"""Audio processing and text cleaning utilities for the voice subsystem."""

from __future__ import annotations

import io
import re
import wave
from app.voice.utils.speech_normalizer import normalize_tts_text


def strip_markdown(text: str, language: str = "en") -> str:
    """Clean, expand, and normalize text for expressive, natural, human-like speech synthesis."""
    if not text:
        return ""

    # Remove Markdown code blocks entirely for spoken output
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Clean raw web URLs so TTS does not spell out character-by-character
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)

    # Extract markdown link text [Text](url) -> Text (BEFORE bracket stripping)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove math LaTeX markers
    text = re.sub(r"\\\((.*?)\\\)", r"\1", text)
    text = re.sub(r"\\\[(.*?)\\\]", r"\1", text)
    text = re.sub(r"\$([^\$]+)\$", r"\1", text)

    # Remove emojis and decorative Unicode symbols that cause robotic pauses or glitches
    text = re.sub(
        r"[\U00010000-\U0010ffff\u2600-\u26ff\u2700-\u27bf\u200d\ufe0f]",
        "",
        text,
    )

    # Remove HTML tags and remaining brackets
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\[\]{}<>]", " ", text)

    # Remove Markdown headers and bold/italic markers
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~`]", "", text)

    # Remove bullet symbols and number list prefixes
    text = re.sub(r"(?m)^\s*[-*+•]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)

    # Remove IPA phonetic symbols/pronunciation guides enclosed in slashes
    text = re.sub(r"/[\u0250-\u02AF\u02B0-\u02FF\u0300-\u036Fˈˌːˑa-zA-Z\s\.-]+/", " ", text)

    # Pass through comprehensive TTS speech normalizer
    text = normalize_tts_text(text, language=language)
    return text.strip()


def parse_wav_header(wav_bytes: bytes) -> tuple[int, int, int]:
    """Parse RIFF WAV header and return (sample_rate, channels, bits_per_sample).

    Falls back to (16000, 1, 16) if parsing fails or input is not a WAV file.
    """
    if not wav_bytes or len(wav_bytes) < 44 or not wav_bytes.startswith(b"RIFF"):
        return 16000, 1, 16

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            bits_per_sample = wf.getsampwidth() * 8
            return sample_rate, channels, bits_per_sample
    except Exception:
        return 16000, 1, 16
