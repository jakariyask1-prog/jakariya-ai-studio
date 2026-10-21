"""Google AI Studio (Gemini) Provider Implementation."""

import os
from typing import Generator, List, Optional
from app.providers.base.base_provider import BaseProvider
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.base.provider_errors import AuthenticationError, ProviderError, RateLimitError
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo


class GoogleAIStudioProvider(BaseProvider):
    """Google AI Studio (Gemini) Provider."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_AI_STUDIO_API_KEY")
        url = base_url or self.DEFAULT_BASE_URL
        super().__init__(provider_id="google_ai_studio", name="Google AI Studio (Gemini)", api_key=key, base_url=url)
        self._client = None

    @property
    def base_url(self) -> str:
        url = super().base_url
        if not url or url.strip() == "https://generativelanguage.googleapis.com":
            return self.DEFAULT_BASE_URL
        if "generativelanguage.googleapis.com" in url and not url.endswith("/v1beta/openai") and not url.endswith("/v1beta/openai/"):
            return "https://generativelanguage.googleapis.com/v1beta/openai/"
        return url

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            supports_chat=True,
            supports_reasoning=True,
            supports_coding=True,
            supports_vision=True,
            supports_stt=True,
            supports_tts=True,
        )

    MODEL_ALIASES = {
        # Legacy/decommissioned models mapped forward to active current models
        "gemini-2.0-flash": "gemini-3.8-flash",
        "gemini-2.5-flash": "gemini-3.8-flash",
        "gemini-2.0-flash-thinking-exp": "gemini-3.7-flash",
        "gemini-1.5-pro": "gemini-pro-latest",
        "gemini-1.5-flash": "gemini-3.5-flash",
        "gemini-3-flash": "gemini-3.8-flash",
    }

    def get_supported_models(self) -> List[ModelInfo]:
        return [
            ModelInfo("google/gemini-3.8-flash", "Gemini 3.8 Flash (Latest Flagship Multimodal)", self.provider_id, context_window=1000000, max_output_tokens=8192, supports_vision=True),
            ModelInfo("google/gemini-3.7-flash", "Gemini 3.7 Flash (Hybrid Reasoning & Fast Coding)", self.provider_id, context_window=1000000, max_output_tokens=8192, supports_vision=True, supports_reasoning=True),
            ModelInfo("google/gemini-3.6-flash", "Gemini 3.6 Flash (Fast Agent & Software Architecture)", self.provider_id, context_window=1000000, max_output_tokens=8192, supports_vision=True),
            ModelInfo("google/gemini-3.5-flash", "Gemini 3.5 Flash (Lightweight & Rapid)", self.provider_id, context_window=1000000, max_output_tokens=8192, supports_vision=True),
            ModelInfo("google/gemini-flash-latest", "Gemini Flash (Auto Latest Stable Flash)", self.provider_id, context_window=1000000, max_output_tokens=8192, supports_vision=True),
            ModelInfo("google/gemini-pro-latest", "Gemini Pro (Auto Latest Deep Reasoning)", self.provider_id, context_window=2000000, max_output_tokens=8192, supports_vision=True, supports_reasoning=True),
        ]

    def validate_api_key(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def _get_client(self):
        current_key = self.api_key
        current_url = self.base_url
        if self._client is None or getattr(self, "_last_key", None) != current_key or getattr(self, "_last_url", None) != current_url:
            if not current_key or len(current_key.strip()) <= 5:
                raise AuthenticationError("Missing or invalid Google AI Studio API key.", provider_id=self.provider_id)
            from openai import OpenAI
            self._client = OpenAI(
                api_key=current_key,
                base_url=current_url,
            )
            self._last_key = current_key
            self._last_url = current_url
        return self._client

    def _format_model_name(self, model: str) -> str:
        """Strip provider prefix and map aliases to verified Google Gemini model endpoints."""
        if model.startswith("google/"):
            model = model[len("google/"):]
        return self.MODEL_ALIASES.get(model.lower(), model)

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
            reasoning = getattr(choice, "reasoning_content", None)
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
            err_msg = str(exc).lower()
            if ("not found" in err_msg or "404" in err_msg) and model_id != "gemini-3.8-flash":
                try:
                    res = client.chat.completions.create(
                        model="gemini-3.8-flash",
                        messages=messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        stream=False,
                    )
                    choice = res.choices[0].message
                    content = choice.content or ""
                    reasoning = getattr(choice, "reasoning_content", None)
                    usage = getattr(res, "usage", None)
                    return ChatResponse(
                        content=content,
                        reasoning_content=reasoning,
                        model="google/gemini-3.8-flash",
                        provider_id=self.provider_id,
                        prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
                        completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
                        total_tokens=getattr(usage, "total_tokens", 0) if usage else 0,
                    )
                except Exception:
                    pass
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
        except Exception as exc:
            err_msg = str(exc).lower()
            if ("not found" in err_msg or "404" in err_msg) and model_id != "gemini-3.8-flash":
                try:
                    res = client.chat.completions.create(
                        model="gemini-3.8-flash",
                        messages=messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                        stream=True,
                    )
                except Exception:
                    self._handle_exception(exc)
            else:
                self._handle_exception(exc)

        try:
            for chunk in res:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "content", None) or ""
                    reasoning = getattr(delta, "reasoning_content", None)
                    finish = chunk.choices[0].finish_reason
                    if text or reasoning or finish:
                        yield StreamChunk(delta=text, reasoning_delta=reasoning, finish_reason=finish)
        except Exception as exc:
            self._handle_exception(exc)

    def _handle_exception(self, exc: Exception) -> None:
        err_str = str(exc)
        if "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower():
            raise AuthenticationError(f"Google AI Studio API Key Error: {err_str}", provider_id=self.provider_id, status_code=401) from exc
        elif "429" in err_str or "rate limit" in err_str.lower() or "quota" in err_str.lower():
            raise RateLimitError(f"Google AI Studio Quota Exceeded: {err_str}", provider_id=self.provider_id, status_code=429) from exc
        else:
            raise ProviderError(f"Google AI Studio API Error: {err_str}", provider_id=self.provider_id) from exc
