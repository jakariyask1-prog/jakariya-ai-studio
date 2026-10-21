"""Cerebras Wafer-Scale AI Provider Implementation."""

import os
from typing import Generator, List, Optional
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import AuthenticationError, ProviderError, RateLimitError
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo


class CerebrasProvider(BaseProvider):
    """Cerebras Wafer-Scale AI Provider."""

    DEFAULT_BASE_URL = "https://api.cerebras.ai/v1"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.getenv("CEREBRAS_API_KEY")
        url = base_url or self.DEFAULT_BASE_URL
        super().__init__(provider_id="cerebras", name="Cerebras Wafer-Scale AI", api_key=key, base_url=url)
        self._client = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_chat=True,
            supports_coding=True,
            supports_reasoning=False,
        )

    MODEL_ALIASES = {
        "llama-3.3-70b": "gpt-oss-120b",
        "llama3.1-8b": "qwen-3.8-27b",
    }

    def get_supported_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("gpt-oss-120b", "GPT OSS 120B (Wafer-Scale 2000+ t/s Reasoning)", self.provider_id, context_window=128000, max_output_tokens=8192),
            ModelInfo("qwen-3.8-27b", "Qwen 3.8 27B (Wafer-Scale Ultra-Fast)", self.provider_id, context_window=32768, max_output_tokens=8192),
        ]

    def validate_api_key(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _get_client(self):
        current_key = self.api_key
        current_url = self.base_url
        if self._client is None or getattr(self, "_last_key", None) != current_key or getattr(self, "_last_url", None) != current_url:
            if not current_key or len(current_key.strip()) <= 5:
                raise AuthenticationError("Missing or invalid Cerebras API key.", provider_id=self.provider_id)
            from openai import OpenAI
            self._client = OpenAI(
                api_key=current_key,
                base_url=current_url,
            )
            self._last_key = current_key
            self._last_url = current_url
        return self._client

    def _format_model_name(self, model: str) -> str:
        if model.startswith("cerebras/"):
            model = model[len("cerebras/"):]
        return self.MODEL_ALIASES.get(model, model)

    def _format_messages(self, request: ChatRequest) -> list:
        msgs = []
        if request.system_prompt:
            msgs.append({"role": "system", "content": request.system_prompt})
        for m in request.messages:
            msgs.append({"role": m.role, "content": self._normalize_content(m.content)})
        return msgs

    @staticmethod
    def _normalize_content(content):
        if not isinstance(content, list):
            return content
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") in ("image", "image_url"):
                    texts.append("[Attached Image]")
        return "\n".join(texts)

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
            usage = getattr(res, "usage", None)
            return ChatResponse(
                content=content,
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
                    finish = chunk.choices[0].finish_reason
                    if text or finish:
                        yield StreamChunk(delta=text, finish_reason=finish)
        except Exception as exc:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        err_str = str(exc)
        if "401" in err_str or "unauthorized" in err_str.lower():
            raise AuthenticationError(f"Cerebras API Key Error: {err_str}", provider_id=self.provider_id, status_code=401) from exc
        elif "429" in err_str or "rate limit" in err_str.lower():
            raise RateLimitError(f"Cerebras Rate Limit Exceeded: {err_str}", provider_id=self.provider_id, status_code=429) from exc
        else:
            raise ProviderError(f"Cerebras API Error: {err_str}", provider_id=self.provider_id) from exc
