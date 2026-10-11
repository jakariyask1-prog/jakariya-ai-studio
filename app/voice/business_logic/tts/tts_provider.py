"""Abstract contract implemented by every text-to-speech provider.

A concrete provider subclasses :class:`TTSProvider` and is registered
with :class:`TTSRegistry`.  The rest of the voice pipeline depends only
on this interface, so providers can be swapped without changing any
calling code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class TTSProvider(ABC):
    """Abstract base class for all text-to-speech providers.

    Concrete implementations must declare a unique :attr:`provider_id`
    and a human-readable :attr:`display_name`.  All audio synthesis and
    API interaction lives inside the subclass; the pipeline only calls
    the abstract methods defined here.
    """

    provider_id: str
    """Unique, stable identifier for this TTS provider.

    Used as the lookup key in :class:`TTSRegistry` and persisted in
    :class:`VoiceSettings`.  Must not change between releases once set.
    Example: ``"elevenlabs"``.
    """

    display_name: str
    """Human-readable name shown in the settings UI.

    Example: ``"ElevenLabs Multilingual v2"``.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` when the provider can accept synthesis requests.

        Implementations should verify that a valid API key is present
        and that any required optional dependency is installed.  This
        check must be fast (no network calls).
        """

    @abstractmethod
    def synthesise(self, text: str, language: str) -> bytes:
        """Convert *text* to raw audio bytes ready for playback.

        Parameters
        ----------
        text:
            The plain text string to synthesise.  Markdown and HTML
            formatting should be stripped by the caller before passing
            text here.
        language:
            BCP-47 language tag (e.g. ``"en"``, ``"bn"``) that the
            provider should use when synthesising speech.

        Returns
        -------
        bytes
            Raw audio data (format depends on the provider, e.g. MP3
            or PCM).  The audio layer is responsible for decoding and
            playing back whatever the provider returns.

        Raises
        ------
        RuntimeError
            When the provider cannot complete synthesis due to an API
            error, network failure, or invalid response.
        """
