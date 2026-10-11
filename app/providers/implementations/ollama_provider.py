"""Ollama Local Offline AI Provider Implementation."""

import os
import logging
from typing import Generator, List, Optional
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import ProviderError, ProviderUnavailableError
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo

logger = logging.getLogger(__name__)


class OllamaProvider(BaseProvider):
    """Ollama Local Offline AI Provider operating over localhost API."""

    DEFAULT_BASE_URL = "http://localhost:11434/v1"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        url = base_url or os.getenv("OLLAMA_BASE_URL") or os.getenv("OLLAMA_HOST") or self.DEFAULT_BASE_URL
        if not url.endswith("/v1") and not url.endswith("/v1/"):
            url = url.rstrip("/") + "/v1"
        key = api_key or os.getenv("OLLAMA_API_KEY") or "ollama"
        super().__init__(provider_id="ollama", name="Ollama Local (Offline)", api_key=key, base_url=url)
        self._client = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_chat=True,
            supports_reasoning=True,
            supports_coding=True,
            supports_vision=True,
        )

    def get_default_models(self) -> List[ModelInfo]:
        """Return static list of supported popular Ollama models."""
        return [
            ModelInfo("llama3.3", "Llama 3.3 (Ollama Local)", self.provider_id, context_window=128000, max_output_tokens=8192),
            ModelInfo("llama3", "Llama 3 (Ollama Local)", self.provider_id, context_window=8192, max_output_tokens=4096),
            ModelInfo("qwen2.5", "Qwen 2.5 (Ollama Local)", self.provider_id, context_window=32768, max_output_tokens=8192),
            ModelInfo("phi3", "Phi-3 (Ollama Local)", self.provider_id, context_window=8192, max_output_tokens=4096),
            ModelInfo("mistral", "Mistral (Ollama Local)", self.provider_id, context_window=32768, max_output_tokens=4096),
            ModelInfo("gemma2", "Gemma 2 (Ollama Local)", self.provider_id, context_window=8192, max_output_tokens=4096),
        ]

    def get_supported_models(self) -> List[ModelInfo]:
        """Discover locally installed models dynamically from Ollama server if running, else return defaults."""
        try:
            client = self._get_client()
            response = client.models.list()
            fetched_models = []
            for item in response.data:
                model_id = item.id
                display_name = f"{model_id} (Ollama Local)"
                fetched_models.append(
                    ModelInfo(model_id, display_name, self.provider_id, context_window=32768, max_output_tokens=8192)
                )
            if fetched_models:
                return fetched_models
        except Exception:
            pass
        return self.get_default_models()

    def validate_api_key(self) -> bool:
        """Return True for Ollama local provider since it doesn't require a remote API key."""
        return bool(self.api_key and str(self.api_key).strip())

    def is_server_running(self) -> bool:
        """Return True if the local Ollama server is reachable at *base_url*.

        This is a lightweight connectivity probe intended for health-check UIs.
        It is intentionally **not** called from ``validate_api_key()`` because:
        - ``validate_api_key()`` tests credential presence, not network state.
        - Failing the ping here would incorrectly exclude Ollama from failover
          candidate lists even when the server might become available shortly.
        """
        try:
            import httpx
            # Strip trailing /v1 to hit the root health endpoint
            base = self.base_url.rstrip("/")
            if base.endswith("/v1"):
                base = base[:-3]
            res = httpx.get(f"{base}/api/tags", timeout=1.0)
            return res.status_code == 200
        except Exception:
            return False

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=0,
                timeout=1.0,
            )
        return self._client

    def _format_model_name(self, model: str) -> str:
        if model.startswith("ollama/"):
            return model[len("ollama/"):]
        return model

    @staticmethod
    def _normalize_content(content):
        if not isinstance(content, list):
            return content
        formatted = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "image":
                source = item.get("source", {})
                media_type = source.get("media_type", "image/png")
                b64_data = source.get("data", "")
                formatted.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{media_type};base64,{b64_data}"
                    }
                })
            else:
                formatted.append(item)
        return formatted

    def _format_messages(self, request: ChatRequest) -> list:
        msgs = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            msgs.append({"role": m.role, "content": self._normalize_content(m.content)})
        return msgs

    def chat(self, request: ChatRequest) -> ChatResponse:
        client = self._get_client()
        messages = self._format_messages(request)
        model_id = self._format_model_name(request.model)
        try:
            res = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False,
            )
            choice = res.choices[0].message
            content = choice.content or ""
            reasoning = getattr(choice, "reasoning_content", None) or getattr(choice, "reasoning", None)
            usage = getattr(res, "usage", None)
            return ChatResponse(
                content=content,
                reasoning_content=reasoning,
                model=request.model,
                provider_id=self.provider_id,
                prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
            )
        except Exception as exc:
            self._handle_exception(exc)

    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        client = self._get_client()
        messages = self._format_messages(request)
        model_id = self._format_model_name(request.model)
        try:
            res = client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=True,
            )
            for chunk in res:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "content", None) or ""
                    reasoning = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
                    finish = chunk.choices[0].finish_reason
                    if text or reasoning or finish:
                        yield StreamChunk(delta=text, reasoning_delta=reasoning, finish_reason=finish)
        except Exception as exc:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        err_str = str(exc)
        if "connection" in err_str.lower() or "refused" in err_str.lower():
            raise ProviderUnavailableError(
                f"Ollama server is not running locally at {self.base_url}. Please start Ollama service (ollama serve).",
                provider_id=self.provider_id,
            ) from exc
        else:
            raise ProviderError(f"Ollama Error: {err_str}", provider_id=self.provider_id) from exc
