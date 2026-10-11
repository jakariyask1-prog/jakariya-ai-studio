"""Plugsky Provider Implementation."""

import os
from typing import Generator, List, Optional
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import AuthenticationError, ProviderError, RateLimitError
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo


class PlugskyProvider(BaseProvider):
    """Plugsky Inference Engine Provider."""

    DEFAULT_BASE_URL = "https://api.plugsky.com/v1"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.getenv("PLUGSKY_API_KEY")
        url = base_url or self.DEFAULT_BASE_URL
        super().__init__(provider_id="plugsky", name="Plugsky AI", api_key=key, base_url=url)
        self._client = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_chat=True,
            supports_reasoning=True,
            supports_coding=True,
            supports_vision=True,
        )

    def get_supported_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("plugsky-lite", "Plugsky Lite (Free)", self.provider_id, context_window=128000, max_output_tokens=8192),
            ModelInfo("plugsky-micro", "Plugsky Micro (Free)", self.provider_id, context_window=128000, max_output_tokens=8192),
            ModelInfo("plugsky-pro", "Plugsky Pro (Paid)", self.provider_id, context_window=128000, max_output_tokens=8192),
            ModelInfo("plugsky-reasoning", "Plugsky Reasoning", self.provider_id, context_window=128000, max_output_tokens=8192, supports_reasoning=True),
            ModelInfo("plugsky-deepseek-pro", "Plugsky DeepSeek Pro", self.provider_id, context_window=128000, max_output_tokens=8192),
        ]

    def validate_api_key(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _get_client(self):
        current_key = self.api_key
        current_url = self.base_url
        if self._client is None or getattr(self, "_last_key", None) != current_key or getattr(self, "_last_url", None) != current_url:
            if not current_key or len(current_key.strip()) <= 5:
                raise AuthenticationError("Missing or invalid Plugsky API key.", provider_id=self.provider_id)
            from openai import OpenAI
            self._client = OpenAI(
                api_key=current_key,
                base_url=current_url,
            )
            self._last_key = current_key
            self._last_url = current_url
        return self._client

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
        try:
            res = client.chat.completions.create(
                model=request.model,
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
        try:
            res = client.chat.completions.create(
                model=request.model,
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
        self._client = None
        err_str = str(exc)
        if "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower():
            raise AuthenticationError(f"Plugsky API Key Error: {err_str}", provider_id=self.provider_id, status_code=401) from exc
        elif "429" in err_str or "rate limit" in err_str.lower():
            raise RateLimitError(f"Plugsky Rate Limit Exceeded: {err_str}", provider_id=self.provider_id, status_code=429) from exc
        else:
            raise ProviderError(f"Plugsky API Error: {err_str}", provider_id=self.provider_id) from exc
