"""Central Provider Manager Factory & Dispatch Engine with Automatic Failover."""

import logging
from typing import Dict, List, Optional, Generator
from app.providers.base.base_provider import BaseProvider
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.base.provider_errors import (
    ProviderError,
    AuthenticationError,
    RateLimitError,
    ProviderUnavailableError,
)
from app.providers.implementations.openrouter_provider import OpenRouterProvider
from app.providers.implementations.google_provider import GoogleAIStudioProvider
from app.providers.implementations.anthropic_provider import AnthropicProvider
from app.providers.implementations.groq_provider import GroqProvider
from app.providers.implementations.cerebras_provider import CerebrasProvider
from app.providers.implementations.ollama_provider import OllamaProvider
from app.providers.implementations.plugsky_provider import PlugskyProvider
from app.providers.implementations.mistral_provider import MistralProvider

logger = logging.getLogger(__name__)


class ProviderManager:
    """Singleton/Factory Dispatcher routing AI requests to registered providers with automatic failover."""

    _instance: Optional['ProviderManager'] = None

    def __init__(self):
        self._providers: Dict[str, BaseProvider] = {}
        # Maps provider_id -> integer priority (lower = higher priority).
        # Kept sorted so _priority_list always reflects the correct failover order.
        self._priority_map: Dict[str, int] = {}
        self._priority_list: List[str] = []

    @classmethod
    def instance(cls) -> 'ProviderManager':
        """Singleton accessor."""
        if cls._instance is None:
            cls._instance = ProviderManager()
            cls._instance.auto_initialize()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for unit testing)."""
        cls._instance = None

    def auto_initialize(self) -> None:
        """Auto-discover and register all core providers from environment/settings."""
        provider_classes = [
            # Groq is the top-priority provider for its ultra-low latency (Live Voice Mode benefit).
            # Plugsky is demoted to priority 50 so it NEVER preempts any real provider during
            # Live Voice turns.  It remains available as a last-resort static fallback.
            (GroqProvider, 2),
            (GoogleAIStudioProvider, 4),
            (OpenRouterProvider, 5),
            (AnthropicProvider, 6),
            (CerebrasProvider, 7),
            (MistralProvider, 8),
            (OllamaProvider, 9),
            (PlugskyProvider, 50),  # Demoted: must never preempt user-selected provider
        ]
        for p_cls, priority in provider_classes:
            try:
                p_inst = p_cls()
                self.register_provider(p_inst, priority=priority)
            except Exception as exc:
                logger.warning(f"Failed to auto-initialize provider {p_cls.__name__}: {exc}")

    def register_provider(self, provider: BaseProvider, priority: int = 10) -> None:
        """Register a provider instance with priority (lower number = higher priority).

        Calling this method with a provider_id that is already registered will
        update its priority and re-sort the failover list accordingly.
        """
        p_id = provider.provider_id
        self._providers[p_id] = provider
        self._priority_map[p_id] = priority
        # Rebuild the priority-sorted list so failover order is always correct.
        self._priority_list = sorted(
            self._priority_map.keys(),
            key=lambda pid: self._priority_map[pid],
        )

    def get_provider(self, provider_id: str) -> Optional[BaseProvider]:
        """Get registered provider instance by ID."""
        return self._providers.get(provider_id)

    def list_providers(self) -> List[str]:
        """Return list of registered provider IDs."""
        return list(self._providers.keys())

    def get_valid_providers(self) -> List[str]:
        """Return list of provider IDs that currently have valid API keys."""
        return [p_id for p_id, p in self._providers.items() if p.validate_api_key()]

    def _prepare_request_for_provider(self, request: ChatRequest, provider: BaseProvider) -> ChatRequest:
        """Ensure the chat request model is compatible with the target failover provider."""
        supported_models = provider.get_supported_models()
        supported_ids = [m.id for m in supported_models]

        # Exact match
        if request.model in supported_ids:
            return request

        # Partial slug match
        norm_name = request.model.split("/", 1)[1] if "/" in request.model else request.model
        for m in supported_models:
            if m.id == norm_name or m.id.endswith("/" + norm_name):
                return ChatRequest(
                    messages=request.messages,
                    model=m.id,
                    system_prompt=request.system_prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=request.stream,
                    web_search=request.web_search,
                    additional_params=request.additional_params,
                )

        # Failover model adaptation: use target provider's default model if request.model is unhosted
        if supported_models:
            fallback_model = supported_models[0].id
            has_images = any(
                isinstance(m.content, list) and any(isinstance(block, dict) and block.get("type") in ("image", "image_url") for block in m.content)
                for m in request.messages
            )
            if has_images:
                vision_models = [m.id for m in supported_models if getattr(m, "supports_vision", False)]
                if vision_models:
                    fallback_model = vision_models[0]
            logger.info(f"[ProviderManager] Adapting failover model '{request.model}' -> '{fallback_model}' for provider '{provider.provider_id}'")
            return ChatRequest(
                messages=request.messages,
                model=fallback_model,
                system_prompt=request.system_prompt,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=request.stream,
                web_search=request.web_search,
                additional_params=request.additional_params,
            )

        return request

    def chat(self, request: ChatRequest, provider_id: Optional[str] = None, is_live: bool = False) -> ChatResponse:
        """Send chat request with automatic failover if the targeted provider fails.

        When ``is_live=True`` (Live Voice Mode) the failover list is restricted so that
        Plugsky — or any provider ranked lower than the user-selected one — is NEVER
        silently substituted.  If the selected provider fails we raise immediately
        rather than hijacking the user's voice session.
        """
        candidate_ids = self._get_candidate_provider_ids(provider_id, is_live=is_live)

        last_exception: Optional[Exception] = None
        for p_id in candidate_ids:
            provider = self._providers[p_id]
            adapted_req = self._prepare_request_for_provider(request, provider)
            try:
                logger.info(f"[ProviderManager] Dispatching chat request to provider '{p_id}' using model '{adapted_req.model}'")
                return provider.chat(adapted_req)
            except (AuthenticationError, RateLimitError, ProviderUnavailableError, ProviderError) as exc:
                logger.warning(f"[ProviderManager] Provider '{p_id}' failed ({exc}). Attempting automatic failover...")
                last_exception = exc
                # In Live Voice Mode: stop at first failure when provider was explicitly selected
                # so we never silently land on Plugsky or a lower-priority provider.
                if is_live and provider_id and p_id == provider_id:
                    break
                continue

        if last_exception:
            raise last_exception
        raise ProviderUnavailableError("No active AI Provider with a valid API Key is available.")

    def chat_stream(self, request: ChatRequest, provider_id: Optional[str] = None, is_live: bool = False) -> Generator[StreamChunk, None, None]:
        """Send streaming chat request with automatic failover before first chunk yields.

        Failover strategy:
        - If a provider raises a known ProviderError, move on to the next candidate.
        - If a provider returns an *empty* stream (StopIteration on first chunk),
          treat it as a transient failure and also try the next candidate instead
          of silently returning an empty response to the caller.

        Live Voice Mode guard (``is_live=True``):
        - When the user has explicitly chosen a provider (``provider_id`` is set),
          we NEVER fall through to Plugsky or any lower-priority provider.
        - On first-provider failure we raise immediately so the pipeline can surface
          a clear error to the user rather than silently hijacking their session.
        """
        candidate_ids = self._get_candidate_provider_ids(provider_id, is_live=is_live)

        primary_exception: Optional[Exception] = None
        last_exception: Optional[Exception] = None
        for p_id in candidate_ids:
            provider = self._providers[p_id]
            adapted_req = self._prepare_request_for_provider(request, provider)
            try:
                logger.info(
                    f"[ProviderManager] Dispatching streaming chat request to provider "
                    f"'{p_id}' using model '{adapted_req.model}'"
                )
                stream = provider.chat_stream(adapted_req)

                # Eagerly consume the first chunk so we can detect an empty stream
                # or a provider error *before* we commit to this provider.
                try:
                    first_chunk = next(stream)
                except StopIteration:
                    # Provider returned an empty stream — treat as a soft failure
                    # and attempt the next candidate instead of silently returning.
                    logger.warning(
                        f"[ProviderManager] Provider '{p_id}' returned an empty stream. "
                        f"Attempting automatic failover..."
                    )
                    # In Live Voice Mode with explicit provider: raise, don't silently shift.
                    if is_live and provider_id and p_id == provider_id:
                        raise ProviderUnavailableError(
                            f"Provider '{p_id}' returned an empty response during Live Voice session."
                        )
                    continue

                # Successfully got the first chunk — yield it and stream the rest.
                yield first_chunk
                yield from stream
                return  # Done — do NOT fall through to further candidates.

            except (AuthenticationError, RateLimitError, ProviderUnavailableError, ProviderError, Exception) as exc:
                logger.warning(
                    f"[ProviderManager] Provider '{p_id}' streaming failed ({exc}). "
                    f"Attempting automatic failover..."
                )
                if p_id == provider_id or primary_exception is None:
                    primary_exception = exc
                last_exception = exc
                # In Live Voice Mode: stop at first failure for user-selected provider
                # so Plugsky or other low-priority providers cannot silently take over.
                if is_live and provider_id and p_id == provider_id:
                    break
                continue

        if primary_exception:
            raise primary_exception
        if last_exception:
            raise last_exception
        raise ProviderUnavailableError("No active AI Provider with a valid API Key is available.")

    def _get_candidate_provider_ids(self, provider_id: Optional[str], is_live: bool = False) -> List[str]:
        """Return ordered list of candidate provider IDs starting with requested or priority valid providers.

        When ``is_live=True`` and a ``provider_id`` is explicitly given, the candidate
        list is limited to ONLY that provider.  This enforces strict provider lock during
        Live Voice Mode so we never silently drift to Plugsky or any fallback provider.
        """
        # Live Voice Mode strict lock: only attempt the user-selected provider.
        if is_live and provider_id and provider_id in self._providers:
            provider = self._providers[provider_id]
            if provider.validate_api_key():
                logger.debug(
                    f"[ProviderManager] Live Voice Mode: strictly using provider '{provider_id}' — no failover."
                )
                return [provider_id]
            # Key invalid but still keep only this provider so the caller gets a
            # clear error rather than a silent Plugsky hijack.
            return [provider_id]

        candidates = []
        if provider_id and provider_id in self._providers:
            provider = self._providers[provider_id]
            if provider_id != "ollama" or not hasattr(provider, "is_server_running") or provider.is_server_running():
                if provider.validate_api_key():
                    candidates.append(provider_id)

        for p_id in self._priority_list:
            # In live voice mode, never silently failover or drift to Plugsky
            if is_live and p_id == "plugsky" and provider_id != "plugsky":
                continue
            if p_id not in candidates and p_id in self._providers:
                p_inst = self._providers[p_id]
                # Skip offline Ollama server during automatic failover to prevent hanging timeouts
                if p_id == "ollama" and hasattr(p_inst, "is_server_running") and not p_inst.is_server_running():
                    continue
                if p_inst.validate_api_key():
                    candidates.append(p_id)

        if not candidates:
            # Fall back to requested or all registered providers even if key validation returned False
            if provider_id and provider_id in self._providers:
                candidates.append(provider_id)
            for p_id in self._priority_list:
                if is_live and p_id == "plugsky" and provider_id != "plugsky":
                    continue
                if p_id not in candidates:
                    p_inst = self._providers[p_id]
                    if p_id == "ollama" and hasattr(p_inst, "is_server_running") and not p_inst.is_server_running():
                        continue
                    candidates.append(p_id)

        return candidates
