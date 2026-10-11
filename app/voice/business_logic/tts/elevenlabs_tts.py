"""ElevenLabs text-to-speech provider.

Uses the ElevenLabs REST API to synthesize natural, expressive speech audio.
"""

from __future__ import annotations

import logging
import os
import requests
from app.voice.business_logic.tts.tts_provider import TTSProvider

logger = logging.getLogger(__name__)


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs text-to-speech provider.

    Synthesises text into audio using ElevenLabs Multilingual models and voice cloning.
    """

    provider_id: str = "elevenlabs"
    display_name: str = "ElevenLabs Multilingual v2"
    DEFAULT_VOICE_ID: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default high quality voice)

    def __init__(
        self,
        voice_id: str = "",
        model_id: str = "eleven_multilingual_v2",
    ) -> None:
        self.voice_id = voice_id or self.DEFAULT_VOICE_ID
        self.model_id = model_id
        self._quota_exceeded: bool = False

    def _get_api_key(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            key = SettingsManager.instance().service.get_api_key("elevenlabs")
            if key:
                return key
        except Exception:
            pass
        return os.getenv("ELEVENLABS_API_KEY", "").strip()

    def _get_voice_id(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            v_id = SettingsManager.instance().service.schema.voice.voice_id
            if v_id and v_id.strip() and not v_id.startswith("bn-BD") and not v_id.startswith("en-US"):
                return v_id.strip()
        except Exception:
            pass
        return self.voice_id or self.DEFAULT_VOICE_ID

    def invalidate_client(self) -> None:
        self._quota_exceeded = False

    def is_available(self) -> bool:
        """Return True when ElevenLabs API key is configured and quota is intact."""
        current_key = self._get_api_key()
        if not current_key:
            return False
        if self._quota_exceeded:
            return False
        return True

    def synthesise(self, text: str, language: str) -> bytes:
        current_key = self._get_api_key()
        if not current_key:
            raise RuntimeError("Missing ElevenLabs API key. Please configure ELEVENLABS_API_KEY in settings.")

        if self._quota_exceeded:
            raise RuntimeError(
                "ElevenLabs TTS quota exceeded. Please check your ElevenLabs subscription or credits."
            )

        if not text.strip() or not any(char.isalnum() for char in text):
            return b""

        try:
            from app.voice.utils.audio_utils import strip_markdown
            clean_text = strip_markdown(text, language=language).strip()
            if not clean_text or not any(char.isalnum() for char in clean_text):
                return b""

            effective_voice_id = self._get_voice_id()
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{effective_voice_id}?output_format=pcm_16000"

            headers = {
                "xi-api-key": current_key,
                "Content-Type": "application/json",
                "Accept": "audio/pcm",
            }

            payload = {
                "text": clean_text,
                "model_id": self.model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            }

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code != 200:
                error_msg = response.text
                if response.status_code == 401:
                    raise RuntimeError(f"ElevenLabs Authentication Error: {error_msg}")
                if response.status_code in (402, 429) or "quota" in error_msg.lower():
                    self._quota_exceeded = True
                    raise RuntimeError("ElevenLabs TTS quota exceeded.")
                raise RuntimeError(f"ElevenLabs TTS synthesis failed ({response.status_code}): {error_msg}")

            return response.content

        except Exception as exc:
            if "quota" in str(exc).lower():
                self._quota_exceeded = True
            raise RuntimeError(f"ElevenLabs TTS synthesis failed: {str(exc)}") from exc
