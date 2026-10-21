"""Groq Whisper Speech-to-Text provider."""

from __future__ import annotations

import logging
import os
import re
import requests
from app.voice.business_logic.stt.stt_provider import STTProvider
from app.voice.utils.speech_normalizer import normalize_stt_transcript

logger = logging.getLogger(__name__)

# Common Whisper phonetic distortions in Bengali and their standard spellings.
# Whisper's tokenizer frequently splits Bengali grapheme clusters inaccurately;
# this normalizer corrects these systematic phonetic errors cleanly.
_BENGALI_PHONETIC_NORMALIZATION = [
    (r"(?<![^\s\.\?!,।])কেমোন(?![^\s\.\?!,।])", "কেমন"),
    (r"(?<![^\s\.\?!,।])ক্যমন(?![^\s\.\?!,।])", "কেমন"),
    (r"(?<![^\s\.\?!,।])ক্যামন(?![^\s\.\?!,।])", "কেমন"),
    (r"(?<![^\s\.\?!,।])অছেন(?![^\s\.\?!,।])", "আছেন"),
    (r"(?<![^\s\.\?!,।])আছোন(?![^\s\.\?!,।])", "আছেন"),
    (r"(?<![^\s\.\?!,।])আচেন(?![^\s\.\?!,।])", "আছেন"),
    (r"(?<![^\s\.\?!,।])আছকের(?![^\s\.\?!,।])", "আজকের"),
    (r"(?<![^\s\.\?!,।])অচকের(?![^\s\.\?!,।])", "আজকের"),
    (r"(?<![^\s\.\?!,।])আজকার(?![^\s\.\?!,।])", "আজকের"),
    (r"(?<![^\s\.\?!,।])আবো\s*হো(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])আবো\s*হাও(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])আবোহ(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])আবভাও(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])আবহাও(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])আপ\s*বহও(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])আপবহও(?![^\s\.\?!,।])", "আবহাওয়া"),
    (r"(?<![^\s\.\?!,।])করচেন(?![^\s\.\?!,।])", "করছেন"),
    (r"(?<![^\s\.\?!,।])করসেন(?![^\s\.\?!,।])", "করছেন"),
    (r"(?<![^\s\.\?!,।])বলচেন(?![^\s\.\?!,।])", "বলছেন"),
    (r"(?<![^\s\.\?!,।])বলসেন(?![^\s\.\?!,।])", "বলছেন"),
    (r"(?<![^\s\.\?!,।])চলচেন(?![^\s\.\?!,।])", "চলছেন"),
    (r"(?<![^\s\.\?!,।])চলসেন(?![^\s\.\?!,।])", "চলছেন"),
    (r"(?<![^\s\.\?!,।])আসচেন(?![^\s\.\?!,।])", "আসছেন"),
    (r"(?<![^\s\.\?!,।])আসসেন(?![^\s\.\?!,।])", "আসছেন"),
    (r"(?<![^\s\.\?!,।])যাচ্চেন(?![^\s\.\?!,।])", "যাচ্ছেন"),
    (r"(?<![^\s\.\?!,।])হচ্চে(?![^\s\.\?!,।])", "হচ্ছে"),
    (r"(?<![^\s\.\?!,।])করচি(?![^\s\.\?!,।])", "করছি"),
    (r"(?<![^\s\.\?!,।])করসি(?![^\s\.\?!,।])", "করছি"),
    (r"(?<![^\s\.\?!,।])বলচি(?![^\s\.\?!,।])", "বলছি"),
    (r"(?<![^\s\.\?!,।])বলসি(?![^\s\.\?!,।])", "বলছি"),
    (r"(?<![^\s\.\?!,।])দেখচি(?![^\s\.\?!,।])", "দেখছি"),
    (r"(?<![^\s\.\?!,।])দেখসি(?![^\s\.\?!,।])", "দেখছি"),
    (r"(?<![^\s\.\?!,।])ধন্নবাদ(?![^\s\.\?!,।])", "ধন্যবাদ"),
    (r"(?<![^\s\.\?!,।])সাহাজ্য(?![^\s\.\?!,।])", "সাহায্য"),
    (r"(?<![^\s\.\?!,।])বাঙলাদেশ(?![^\s\.\?!,।])", "বাংলাদেশ"),
    (r"(?<![^\s\.\?!,।])বাংগালী(?![^\s\.\?!,।])", "বাঙালি"),
    (r"(?<![^\s\.\?!,।])বাঙ্গালী(?![^\s\.\?!,।])", "বাঙালি"),
    (r"(?<![^\s\.\?!,।])বাঙলা(?![^\s\.\?!,।])", "বাংলা"),
    (r"(?<![^\s\.\?!,।])কস্ট(?![^\s\.\?!,।])", "কষ্ট"),
    (r"(?<![^\s\.\?!,।])সুন্দোর(?![^\s\.\?!,।])", "সুন্দর"),
]


class GroqSTT(STTProvider):
    """STTProvider implementation using Groq Cloud Whisper API.

    Provides high-speed speech transcription using whisper-large-v3,
    with full support for Bengali (bn) and English (en).
    Eliminates artificial meta-prompt contamination that causes Whisper to
    hallucinate foreign languages or scramble Bengali spellings.
    """

    provider_id = "groq_stt"
    display_name = "Groq Whisper (Ultra-Fast)"

    def __init__(self, model_id: str = "whisper-large-v3") -> None:
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

    def _normalize_bengali_text(self, text: str) -> str:
        """Correct common Whisper Bengali phonetic spelling errors."""
        if not text or not any("\u0980" <= ch <= "\u09ff" for ch in text):
            return text
        res = text
        for pattern, repl in _BENGALI_PHONETIC_NORMALIZATION:
            res = re.sub(pattern, repl, res)
        return res

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

            clean_lang = str(language or "").strip().lower()
            if clean_lang.startswith("bn") or clean_lang in ("bangla", "bengali"):
                data["language"] = "bn"
            elif clean_lang.startswith("en") or clean_lang == "english":
                data["language"] = "en"
            elif clean_lang not in ("auto", "all", ""):
                lang_code = clean_lang.split("-")[0]
                if lang_code in ("hi", "ar", "es", "fr", "de", "zh", "ja", "ru", "pt", "it"):
                    data["language"] = lang_code
            # Notice: When language is "auto", we intentionally do NOT force data["language"]
            # and do NOT inject meta-instruction prompts ("Bangla and English...", "শুদ্ধ বানান").
            # Whisper is an acoustic sequence-to-sequence model; injecting artificial prompts
            # severely confuses its language classifier and corrupts Bengali spelling.

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
            raw_text = result.get("text", "").strip()

            # Apply comprehensive bilingual phonetic & orthographic normalization
            normalized = normalize_stt_transcript(raw_text, language=clean_lang)
            return self._normalize_bengali_text(normalized)

        except Exception as exc:
            logger.exception("Failed to transcribe audio via Groq STT")
            raise RuntimeError(f"Groq STT error: {exc}") from exc
