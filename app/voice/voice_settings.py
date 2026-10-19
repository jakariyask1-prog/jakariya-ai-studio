"""User-configurable voice system settings.

A plain dataclass with no Qt or provider dependencies so it can be
serialised, compared, and passed freely between all voice layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoiceSettings:
    """Holds all user-configurable parameters for the voice pipeline.

    Default values represent a sensible out-of-the-box configuration.
    Individual fields are intentionally kept simple so they can be
    persisted to a config file and restored at startup without any
    special serialisation logic.
    """

    # --- Provider selection -------------------------------------------

    stt_provider_id: str = "groq_stt"
    """Identifier of the active speech-to-text provider.

    Must match a ``provider_id`` registered in :class:`STTRegistry`.
    """

    tts_provider_id: str = "edge_neural_tts"
    """Identifier of the active text-to-speech provider.

    Must match a ``provider_id`` registered in :class:`TTSRegistry`.
    """

    voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    """Voice identifier string for TTS engines (e.g., ElevenLabs Voice ID)."""

    custom_voices: list[dict[str, Any]] = field(default_factory=list)
    """User-added custom or cloned voice entries [{\"id\": ..., \"name\": ..., \"provider_id\": ...}]."""

    # --- Language / locale -------------------------------------------

    language: str = "en"
    """BCP-47 language tag used by both STT and TTS providers.

    Common values: ``"en"`` (English), ``"bn"`` (Bangla).
    Providers may support a subset of locales; consult their documentation.
    """

    # --- Audio device selection --------------------------------------

    input_device_index: int | None = None
    """System audio input device index for microphone capture.

    ``None`` selects the OS default input device.
    """

    output_device_index: int | None = None
    """System audio output device index for playback.

    ``None`` selects the OS default output device.
    """

    # --- Behaviour flags & VAD sensitivity ---------------------------

    auto_send: bool = False
    """When ``True``, a transcribed utterance is sent to Claude automatically
    without the user pressing Send. Default is False.
    """

    voice_response: bool = True
    """When ``True``, Claude's text reply is passed to the TTS provider
    and spoken aloud.  When ``False``, only the text is shown.
    """

    silence_timeout_ms: int = 550
    """Silence duration in milliseconds before auto-sending audio (550ms = snappy and responsive)."""

    vad_threshold: float = 0.020
    """Voice Activity Detection energy threshold."""
