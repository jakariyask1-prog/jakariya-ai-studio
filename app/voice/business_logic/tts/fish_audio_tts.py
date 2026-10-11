"""Fish Audio text-to-speech provider.

Uses the Fish Audio REST API to synthesize speech audio from text.
"""

from __future__ import annotations

import os
import requests
from app.voice.business_logic.tts.tts_provider import TTSProvider


class FishAudioTTS(TTSProvider):
    """Fish Audio text-to-speech provider.

    Synthesises text into audio using Fish Audio models (defaulting to s2.1-pro).
    """

    provider_id: str = "fish_audio"
    display_name: str = "Fish Audio TTS"

    def __init__(
        self,
        voice_id: str = "",
        model_id: str = "s2.1-pro",
        output_format: str = "pcm",
    ) -> None:
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format
        self._quota_exceeded: bool = False

    def _get_api_key(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            key = SettingsManager.instance().service.get_api_key("fish_audio")
            if key:
                return key
        except Exception:
            pass
        return os.getenv("FISH_AUDIO_API_KEY", "").strip()

    def _get_voice_id(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            v_id = SettingsManager.instance().service.schema.voice.voice_id
            if v_id and v_id.strip() and not v_id.startswith("bn-BD") and not v_id.startswith("en-US"):
                return v_id.strip()
        except Exception:
            pass
        return self.voice_id or ""

    def invalidate_client(self) -> None:
        self._quota_exceeded = False

    def is_available(self) -> bool:
        """Return True when the API key is present."""
        if self._quota_exceeded:
            return False
        return bool(self._get_api_key())

    def synthesise(self, text: str, language: str) -> bytes:
        if self._quota_exceeded:
            raise RuntimeError("Fish Audio TTS quota exceeded.")

        if not text.strip() or not any(char.isalnum() for char in text):
            return b""

        try:
            from app.voice.utils.audio_utils import strip_markdown
            clean_text = strip_markdown(text, language=language).strip()
            if not clean_text or not any(char.isalnum() for char in clean_text):
                return b""

            headers = {
                "Authorization": f"Bearer {self._get_api_key()}",
                "Content-Type": "application/json"
            }

            payload = {
                "text": clean_text,
                "format": self.output_format,
                "sample_rate": 16000
            }

            ref_id = self._get_voice_id()
            if ref_id:
                payload["reference_id"] = ref_id

            response = requests.post(
                "https://api.fish.audio/v1/tts",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                error_msg = response.text
                if response.status_code == 402 or "quota" in error_msg.lower():
                    self._quota_exceeded = True
                raise RuntimeError(f"Fish Audio TTS synthesis failed: {response.status_code} - {error_msg}")

            return response.content

        except Exception as exc:
            raise RuntimeError(f"Fish Audio TTS synthesis failed: {str(exc)}") from exc
