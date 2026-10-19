"""Groq Whisper Speech-to-Text provider."""

from __future__ import annotations

import logging
import os
import requests
from app.voice.business_logic.stt.stt_provider import STTProvider

logger = logging.getLogger(__name__)


class GroqSTT(STTProvider):
    """STTProvider implementation using Groq Cloud Whisper API.

    Provides ultra-low latency (~150-250ms) speech transcription using
    the whisper-large-v3-turbo model, with full support for Bengali (bn)
    and English (en).
    """

    provider_id = "groq_stt"
    display_name = "Groq Whisper (Ultra-Fast)"

    def __init__(self, model_id: str = "whisper-large-v3-turbo") -> None:
        self.model_id = model_id

    def _get_api_key(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            key = SettingsManager.instance().service.get_api_key("groq")
            if key:
                return key
        except Exception:
            pass
        return os.getenv("GROQ_API_KEY", "").strip()

    def is_available(self) -> bool:
        """Return True when Groq API key is configured."""
        return bool(self._get_api_key())

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        """Transcribe WAV audio bytes using Groq Whisper API."""
        if not audio_bytes:
            return ""

        key = self._get_api_key()
        if not key:
            raise RuntimeError("Missing Groq API key for STT transcription.")

        try:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {
                "Authorization": f"Bearer {key}",
            }
            files = {
                "file": ("audio.wav", audio_bytes, "audio/wav"),
            }
            data: dict[str, str] = {
                "model": self.model_id,
                "response_format": "json",
            }

            if language:
                lang_code = language.strip().lower()
                if "-" in lang_code:
                    lang_code = lang_code.split("-")[0]
                if lang_code in ("bn", "en", "hi", "ar", "es", "fr", "de", "zh", "ja", "ru", "pt", "it"):
                    data["language"] = lang_code

            response = requests.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=12,
            )

            if response.status_code != 200:
                logger.warning("Groq STT error: %s - %s", response.status_code, response.text)
                raise RuntimeError(f"Groq STT failed ({response.status_code}): {response.text}")

            result = response.json()
            return result.get("text", "").strip()

        except Exception as exc:
            logger.exception("Failed to transcribe audio via Groq STT")
            raise RuntimeError(f"Groq STT error: {exc}") from exc
