"""ElevenLabs Speech-to-Text (Scribe) provider."""

from __future__ import annotations

import logging
import os
import requests
from app.voice.business_logic.stt.stt_provider import STTProvider

logger = logging.getLogger(__name__)


class ElevenLabsSTT(STTProvider):
    """STTProvider implementation using ElevenLabs Scribe API.

    Provides high-accuracy multi-lingual speech transcription.
    """

    provider_id = "elevenlabs_stt"
    display_name = "ElevenLabs Scribe v2"

    def __init__(self, model_id: str = "scribe_v1") -> None:
        self.model_id = model_id

    def _get_api_key(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            key = SettingsManager.instance().service.get_api_key("elevenlabs")
            if key:
                return key
        except Exception:
            pass
        return os.getenv("ELEVENLABS_API_KEY", "").strip()

    def is_available(self) -> bool:
        """Return True when ElevenLabs API key is configured."""
        return bool(self._get_api_key())

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        """Transcribe WAV audio bytes using ElevenLabs Scribe API."""
        if not audio_bytes:
            return ""

        key = self._get_api_key()
        if not key:
            raise RuntimeError("Missing ElevenLabs API key for STT transcription.")

        try:
            url = "https://api.elevenlabs.io/v1/speech-to-text"
            headers = {
                "xi-api-key": key,
            }
            files = {
                "file": ("audio.wav", audio_bytes, "audio/wav"),
            }
            data = {
                "model_id": self.model_id,
            }
            if language:
                lang_code = language.strip().lower()
                if "-" in lang_code:
                    lang_code = lang_code.split("-")[0]
                data["language_code"] = lang_code

            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=30,
            )

            if response.status_code != 200:
                logger.warning("ElevenLabs STT error: %s - %s", response.status_code, response.text)
                raise RuntimeError(f"ElevenLabs STT failed ({response.status_code}): {response.text}")

            result = response.json()
            return result.get("text", "").strip()

        except Exception as exc:
            logger.exception("Failed to transcribe audio via ElevenLabs STT")
            raise RuntimeError(f"ElevenLabs STT error: {exc}") from exc
