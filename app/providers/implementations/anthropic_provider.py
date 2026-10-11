"""Anthropic Claude Direct Provider Implementation."""

import os
from typing import Generator, List, Optional
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import AuthenticationError, ProviderError, RateLimitError
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo


class AnthropicProvider(BaseProvider):
    """Anthropic Claude Direct SDK/API Provider."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        super().__init__(provider_id="anthropic", name="Anthropic Direct", api_key=key, base_url=base_url)
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
            ModelInfo("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet", self.provider_id, context_window=200000, max_output_tokens=8192, supports_vision=True),
            ModelInfo("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", self.provider_id, context_window=200000, max_output_tokens=8192, supports_vision=True),
            ModelInfo("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", self.provider_id, context_window=200000, max_output_tokens=8192),
            ModelInfo("claude-3-opus-20240229", "Claude 3 Opus", self.provider_id, context_window=200000, max_output_tokens=4096, supports_vision=True),
        ]

    def validate_api_key(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _get_client(self):
        if self._client is None:
            if not self.validate_api_key():
                raise AuthenticationError("Missing or invalid Anthropic API key.", provider_id=self.provider_id)
            from anthropic import Anthropic
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def _format_model_name(self, model: str) -> str:
        if model.startswith("anthropic/"):
            model = model[len("anthropic/"):]
        if model in ("claude-3-7-sonnet", "claude-3.7-sonnet", "claude-3-7-sonnet-20250219"):
            return "claude-3-7-sonnet-20250219"
        if model in ("claude-3.5-sonnet", "claude-sonnet-3.5", "claude-3-5-sonnet"):
            return "claude-3-5-sonnet-20241022"
        if model in ("claude-3.5-haiku", "claude-haiku-3.5", "claude-3-5-haiku"):
            return "claude-3-5-haiku-20241022"
        if model in ("claude-3-opus", "claude-opus"):
            return "claude-3-opus-20240229"
        return model

    def _format_messages(self, request: ChatRequest) -> list:
        msgs = []
        for m in request.messages:
            if m.role in ("user", "assistant"):
                msgs.append({"role": m.role, "content": m.content})
        return msgs

    def chat(self, request: ChatRequest) -> ChatResponse:
        client = self._get_client()
        messages = self._format_messages(request)
        model_id = self._format_model_name(request.model)
        system_prompt = request.system_prompt or ""
        try:
            kwargs = {
                "model": model_id,
                "max_tokens": request.max_tokens,
                "messages": messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            res = client.messages.create(**kwargs)
            content_blocks = getattr(res, "content", [])
            text_out = "".join([getattr(b, "text", "") for b in content_blocks if getattr(b, "type", "") == "text"])
            usage = getattr(res, "usage", None)
            return ChatResponse(
                content=text_out,
                model=request.model,
                provider_id=self.provider_id,
                prompt_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
                completion_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
                total_tokens=(getattr(usage, "input_tokens", 0) + getattr(usage, "output_tokens", 0)) if usage else 0,
            )
        except Exception as exc:
            self._handle_exception(exc)

    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        client = self._get_client()
        messages = self._format_messages(request)
        model_id = self._format_model_name(request.model)
        system_prompt = request.system_prompt or ""
        try:
            kwargs = {
                "model": model_id,
                "max_tokens": request.max_tokens,
                "messages": messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            with client.messages.stream(**kwargs) as stream:
                for event in stream:
                    if getattr(event, "type", None) == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if getattr(delta, "type", None) == "text_delta":
                            text = getattr(delta, "text", "")
                            if text:
                                yield StreamChunk(delta=text)
        except Exception as exc:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        err_str = str(exc)
        if "401" in err_str or "authentication_error" in err_str.lower():
            raise AuthenticationError(f"Anthropic API Key Error: {err_str}", provider_id=self.provider_id, status_code=401) from exc
        elif "429" in err_str or "rate_limit_error" in err_str.lower():
            raise RateLimitError(f"Anthropic Rate Limit Exceeded: {err_str}", provider_id=self.provider_id, status_code=429) from exc
        else:
            raise ProviderError(f"Anthropic API Error: {err_str}", provider_id=self.provider_id) from exc
