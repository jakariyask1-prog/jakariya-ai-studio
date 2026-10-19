"""Cartesia AI text-to-speech provider.

Uses the Cartesia REST API to synthesize ultra-fast, expressive speech audio.
"""

from __future__ import annotations

import os
import requests
from app.voice.business_logic.tts.tts_provider import TTSProvider


class CartesiaTTS(TTSProvider):
    """Cartesia AI text-to-speech provider.

    Synthesises text into audio using Cartesia's Sonic model.
    """

    provider_id: str = "cartesia"
    display_name: str = "Cartesia AI"
    DEFAULT_BANGLA_VOICE_ID: str = "2c8d7dfb-ca84-4888-9600-8d8c54022dba"
    DEFAULT_ENGLISH_VOICE_ID: str = "e8299d96-b115-4ed1-80aa-2696eb5335ca"

    def __init__(
        self,
        voice_id: str = "694f9389-aac1-45b6-b726-9d9369183238", # Default British Lady voice or standard voice
        model_id: str = "sonic-latest",
    ) -> None:
        self.voice_id = voice_id
        self.model_id = model_id
        self._quota_exceeded: bool = False

    def _get_api_key(self) -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            key = SettingsManager.instance().service.get_api_key("cartesia")
            if key:
                return key
        except Exception:
            pass
        return os.getenv("CARTESIA_API_KEY", "").strip()

    def _get_voice_id(self, language: str = "") -> str:
        try:
            from app.settings.settings_manager import SettingsManager
            schema_voice = SettingsManager.instance().service.schema.voice
            v_id = schema_voice.voice_id
            effective_lang = language or getattr(schema_voice, "language", "")

            # If user selected either of their personal cloned voices, match voice to language
            if v_id in (self.DEFAULT_BANGLA_VOICE_ID, self.DEFAULT_ENGLISH_VOICE_ID):
                if effective_lang and str(effective_lang).lower().startswith("en"):
                    return self.DEFAULT_ENGLISH_VOICE_ID
                return self.DEFAULT_BANGLA_VOICE_ID

            if v_id and v_id.strip() and not v_id.startswith("bn-BD") and not v_id.startswith("en-US"):
                return v_id.strip()
        except Exception:
            pass
        if language and str(language).lower().startswith("en"):
            return self.DEFAULT_ENGLISH_VOICE_ID
        return self.voice_id or self.DEFAULT_BANGLA_VOICE_ID

    def invalidate_client(self) -> None:
        self._quota_exceeded = False

    def is_available(self) -> bool:
        current_key = self._get_api_key()
        if not current_key:
            return False
        if getattr(self, "_last_api_key", "") != current_key:
            self._last_api_key = current_key
            self._quota_exceeded = False
        if self._quota_exceeded:
            return False
        return True

    def synthesise(self, text: str, language: str) -> bytes:
        current_key = self._get_api_key()
        if getattr(self, "_last_api_key", "") != current_key:
            self._last_api_key = current_key
            self._quota_exceeded = False
        if self._quota_exceeded:
            raise RuntimeError(
                "Cartesia TTS credits limit reached (402 Quota Exceeded). "
                "Please recharge at https://play.cartesia.ai/subscription."
            )

        if not text.strip() or not any(char.isalnum() for char in text):
            return b""

        try:
            from app.voice.utils.audio_utils import strip_markdown
            clean_text = strip_markdown(text, language=language).strip()
            if not clean_text or not any(char.isalnum() for char in clean_text):
                return b""

            headers = {
                "Cartesia-Version": "2024-06-10",
                "X-API-Key": current_key,
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json",
            }

            import uuid
            effective_voice_id = self._get_voice_id(language=language)
            try:
                uuid.UUID(str(effective_voice_id).strip())
            except (ValueError, AttributeError):
                effective_voice_id = (
                    self.DEFAULT_ENGLISH_VOICE_ID
                    if (language and str(language).lower().startswith("en"))
                    else self.DEFAULT_BANGLA_VOICE_ID
                )

            # Detect Bengali characters or check language setting
            has_bengali = any("\u0980" <= ch <= "\u09ff" for ch in clean_text)
            lang_code = "bn" if (has_bengali or (language and str(language).lower().startswith("bn"))) else "en"

            payload = {
                "model_id": self.model_id,
                "transcript": clean_text,
                "voice": {"mode": "id", "id": str(effective_voice_id).strip()},
                "output_format": {
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": 16000
                },
                "language": lang_code,
            }

            response = requests.post(
                "https://api.cartesia.ai/tts/bytes",
                headers=headers,
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                error_msg = response.text
                if response.status_code == 402 or "quota" in error_msg.lower() or "credits limit" in error_msg.lower():
                    self._quota_exceeded = True
                    raise RuntimeError(
                        "Cartesia TTS credits limit reached (402 Quota Exceeded). "
                        "Please recharge at https://play.cartesia.ai/subscription "
                        "or switch to Edge Neural TTS (100% Free)."
                    )
                raise RuntimeError(f"Cartesia TTS synthesis failed: {response.status_code} - {error_msg}")

            return response.content

        except Exception as exc:
            raise RuntimeError(f"Cartesia TTS synthesis failed: {str(exc)}") from exc
