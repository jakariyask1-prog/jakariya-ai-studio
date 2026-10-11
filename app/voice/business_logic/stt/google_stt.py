"""Google Web Speech API STT provider."""

from __future__ import annotations

import io
import logging
import warnings

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import speech_recognition as sr

from app.voice.business_logic.stt.stt_provider import STTProvider
from app.voice.utils.patch_speech import patch_speech_recognition

# Ensure speech_recognition FLAC converter is patched in windowed and frozen modes
patch_speech_recognition()


class GoogleSTT(STTProvider):
    """STTProvider implementation using Google Web Speech API.

    This is a free service provided by Google that doesn't require an API key,
    though it has rate limits and is intended for prototyping.
    """

    provider_id = "google_stt"
    display_name = "Google STT (Free)"

    def is_available(self) -> bool:
        """Return True since this uses the free Google API."""
        return True

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        """Transcribe WAV audio bytes to text using Google's Web Speech API."""
        if not audio_bytes:
            return ""

        try:
            # The input is a standard WAV from our microphone
            wav_io = io.BytesIO(audio_bytes)
            
            recognizer = sr.Recognizer()
            with sr.AudioFile(wav_io) as source:
                audio_data = recognizer.record(source)

            # Map language to BCP-47 tag. (e.g. 'bn-BD' for Bengali, 'en-US' for English)
            # Standardize language tags for Google API
            lang_code = language.strip().lower()
            if lang_code == "bn":
                lang_code = "bn-BD"
            elif lang_code == "en":
                lang_code = "en-US"
            else:
                lang_code = language  # Pass through directly if it's something else

            text = recognizer.recognize_google(audio_data, language=lang_code)
            return text
        except sr.UnknownValueError:
            return ""  # Audio was incomprehensible
        except sr.RequestError as exc:
            logging.exception("Google STT API error")
            raise RuntimeError(f"Google STT service is unavailable: {exc}") from exc
        except Exception as exc:
            logging.exception("Failed to transcribe audio via Google STT")
            raise RuntimeError(f"Google STT processing failed: {exc}") from exc
