"""Voice service — bridges voice business logic to provider registries.

:class:`VoiceService` is the single point of contact between the
:class:`VoiceManager` and the STT/TTS provider registries.  It contains
no audio capture or playback logic; those responsibilities belong to the
concrete providers and to a future audio layer.
"""

from __future__ import annotations

import logging

from app.voice.business_logic.stt.stt_provider import STTProvider
from app.voice.business_logic.stt.stt_registry import STTRegistry
from app.voice.business_logic.tts.tts_provider import TTSProvider
from app.voice.business_logic.tts.tts_registry import TTSRegistry
from app.voice.voice_settings import VoiceSettings

logger = logging.getLogger(__name__)


class VoiceService:
    """Coordinate STT and TTS provider resolution for the voice pipeline.

    The service owns the provider registries and exposes a minimal API
    that the manager can call without knowing which concrete providers
    are installed.  API calls and audio I/O are intentionally absent
    from this layer; they live inside each :class:`STTProvider` or
    :class:`TTSProvider` implementation.
    """

    def __init__(
        self,
        stt_registry: STTRegistry,
        tts_registry: TTSRegistry,
        settings: VoiceSettings | None = None,
    ) -> None:
        self._stt_registry = stt_registry
        self._tts_registry = tts_registry
        self._settings = settings or VoiceSettings()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    @property
    def settings(self) -> VoiceSettings:
        """Return the current voice settings."""
        return self._settings

    def update_settings(self, settings: VoiceSettings) -> None:
        """Replace the active settings with a new configuration."""
        self._settings = settings

    # ------------------------------------------------------------------
    # STT provider access
    # ------------------------------------------------------------------

    def active_stt_provider(self) -> STTProvider:
        """Return the STT provider selected in current settings with automatic fallback to any available STT provider."""
        pid = (self._settings.stt_provider_id or "google_stt").strip()
        try:
            provider = self._stt_registry.get(pid)
            if provider.is_available():
                return provider
            logger.warning(
                "[VoiceService] STT provider '%s' is not available (check API key). Falling back.", pid
            )
        except Exception:
            logger.warning("[VoiceService] STT provider '%s' not found in registry.", pid)

        for prov in self._stt_registry.available_providers():
            if prov.is_available():
                logger.info("[VoiceService] Using fallback STT provider: %s", prov.provider_id)
                return prov
        raise RuntimeError("No STT provider is available.")

    def get_stt_provider(self, provider_id: str) -> STTProvider | None:
        """Return a registered STT provider by ID, or None if not found."""
        try:
            return self._stt_registry.get(provider_id)
        except Exception:
            return None

    def available_stt_providers(self) -> tuple[STTProvider, ...]:
        """Return all registered STT providers for display in settings UI."""
        return self._stt_registry.available_providers()

    # ------------------------------------------------------------------
    # TTS provider access
    # ------------------------------------------------------------------

    def active_tts_provider(self) -> TTSProvider:
        """Return the TTS provider selected in current settings with automatic fallback to any available TTS provider."""
        pid = (self._settings.tts_provider_id or "edge_neural_tts").strip()
        try:
            provider = self._tts_registry.get(pid)
            if provider.is_available():
                return provider
            logger.warning(
                "[VoiceService] TTS provider '%s' is not available (check API key). Falling back.", pid
            )
        except Exception:
            logger.warning("[VoiceService] TTS provider '%s' not found in registry.", pid)

        for prov in self._tts_registry.available_providers():
            if prov.is_available():
                logger.info("[VoiceService] Using fallback TTS provider: %s", prov.provider_id)
                return prov
        raise RuntimeError("No TTS provider is available.")

    def get_tts_provider(self, provider_id: str) -> TTSProvider | None:
        """Return a registered TTS provider by ID, or None if not found."""
        try:
            return self._tts_registry.get(provider_id)
        except Exception:
            return None

    def available_tts_providers(self) -> tuple[TTSProvider, ...]:
        """Return all registered TTS providers for display in settings UI."""
        return self._tts_registry.available_providers()

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        """Return ``True`` when both active providers are configured and available.

        A ``False`` return means the pipeline cannot start a voice turn
        and the UI should prompt the user to configure their providers.
        """
        try:
            stt_ok = self.active_stt_provider().is_available()
            tts_ok = (
                self.active_tts_provider().is_available()
                if self._settings.voice_response
                else True
            )
            return stt_ok and tts_ok
        except Exception:
            return False
