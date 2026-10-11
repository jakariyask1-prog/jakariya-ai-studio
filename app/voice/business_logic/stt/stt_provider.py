"""Abstract contract implemented by every speech-to-text provider.

A concrete provider subclasses :class:`STTProvider` and is registered
with :class:`STTRegistry`.  The rest of the voice pipeline depends only
on this interface, so providers can be swapped without changing any
calling code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class STTProvider(ABC):
    """Abstract base class for all speech-to-text providers.

    Concrete implementations must declare a unique :attr:`provider_id`
    and a human-readable :attr:`display_name`.  All audio capture and
    API interaction lives inside the subclass; the pipeline only calls
    the abstract methods defined here.
    """

    provider_id: str
    """Unique, stable identifier for this STT provider.

    Used as the lookup key in :class:`STTRegistry` and persisted in
    :class:`VoiceSettings`.  Must not change between releases once set.
    Example: ``"deepgram"``.
    """

    display_name: str
    """Human-readable name shown in the settings UI.

    Example: ``"Deepgram Nova-3"``.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` when the provider can accept requests.

        Implementations should verify that a valid API key is present
        and that any required optional dependency is installed.  This
        check must be fast (no network calls).
        """

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        """Convert raw audio bytes to a transcript string.

        Parameters
        ----------
        audio_bytes:
            Raw PCM or encoded audio captured from the microphone.
        language:
            BCP-47 language tag (e.g. ``"en"``, ``"bn"``) that the
            provider should use when decoding the audio.

        Returns
        -------
        str
            The transcribed text.  Returns an empty string when no
            speech was detected.

        Raises
        ------
        RuntimeError
            When the provider cannot complete transcription due to an
            API error, network failure, or invalid response.
        """
