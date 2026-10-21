"""Free Google Translate Text-to-Speech provider using gTTS."""

from __future__ import annotations

import io
import logging
from app.voice.business_logic.tts.tts_provider import TTSProvider


class GoogleTTS(TTSProvider):
    """TTSProvider implementation using Google Translate TTS (gTTS)."""

    provider_id = "google_tts"
    display_name = "Google TTS (Free)"

    def is_available(self) -> bool:
        """Return True since gTTS doesn't require API keys."""
        return True

    def synthesise(self, text: str, language: str) -> bytes:
        """Convert text to raw PCM audio bytes using gTTS and miniaudio."""
        from app.voice.utils.audio_utils import strip_markdown

        clean_text = strip_markdown(text, language=language).strip()
        if not clean_text or not any(char.isalnum() for char in clean_text):
            return b""

        try:
            from gtts import gTTS
            import miniaudio

            has_bengali = any("\u0980" <= char <= "\u09ff" for char in clean_text)
            lang_code = language.strip().lower() if language else "en"
            if has_bengali or lang_code.startswith("bn"):
                lang_code = "bn"
            elif lang_code.startswith("en"):
                lang_code = "en"
            else:
                lang_code = lang_code.split("-")[0]

            mp3_fp = io.BytesIO()
            tts = gTTS(text=clean_text, lang=lang_code)
            tts.write_to_fp(mp3_fp)
            mp3_bytes = mp3_fp.getvalue()

            if not mp3_bytes:
                return b""

            decoded = miniaudio.decode(mp3_bytes, nchannels=1, sample_rate=16000)
            return decoded.samples.tobytes()

        except Exception as exc:
            logging.exception(f"Google TTS synthesis failed for text: {text[:50]}...")
            raise RuntimeError(f"Google TTS synthesis failed: {exc}") from exc
