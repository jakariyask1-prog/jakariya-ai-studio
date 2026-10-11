"""Registry that resolves STT providers without conditional chains.

Concrete :class:`STTProvider` implementations are registered once at
application startup.  The voice pipeline resolves them by provider ID,
keeping the calling code decoupled from any specific provider.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.voice.business_logic.stt.stt_provider import STTProvider


class UnknownSTTProviderError(LookupError):
    """Raised when no registered STT provider matches a requested ID."""


class STTRegistry:
    """Map a provider identifier to exactly one STTProvider implementation.

    Providers are registered at startup and looked up by the voice
    pipeline when a voice turn begins.  Duplicate registrations and
    incomplete providers are rejected at registration time so problems
    surface early.
    """

    def __init__(self, providers: Iterable[STTProvider] = ()) -> None:
        self._providers: dict[str, STTProvider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: STTProvider) -> None:
        """Add a provider to the registry.

        Parameters
        ----------
        provider:
            A concrete :class:`STTProvider` instance to register.

        Raises
        ------
        ValueError
            When a provider with the same ``provider_id`` is already
            registered, or when ``provider_id`` or ``display_name``
            is missing.
        """
        provider_id = provider.provider_id.strip()
        if not provider_id:
            raise ValueError("STTProvider must define a non-empty provider_id.")
        if not getattr(provider, "display_name", "").strip():
            raise ValueError(
                f"STTProvider '{provider_id}' must define a display_name."
            )
        if provider_id in self._providers:
            raise ValueError(
                f"An STT provider with id '{provider_id}' is already registered."
            )
        self._providers[provider_id] = provider

    def get(self, provider_id: str) -> STTProvider:
        """Return the provider for *provider_id* or raise a clear error.

        Raises
        ------
        UnknownSTTProviderError
            When no provider matching *provider_id* has been registered.
        """
        try:
            return self._providers[provider_id.strip()]
        except KeyError as error:
            available = ", ".join(self.available_ids()) or "none"
            raise UnknownSTTProviderError(
                f"STT provider '{provider_id}' is not registered. "
                f"Available: {available}."
            ) from error

    def available_ids(self) -> tuple[str, ...]:
        """Return all registered provider IDs in alphabetical order."""
        return tuple(sorted(self._providers))

    def available_providers(self) -> tuple[STTProvider, ...]:
        """Return all registered providers in alphabetical ID order."""
        return tuple(
            self._providers[pid] for pid in sorted(self._providers)
        )
