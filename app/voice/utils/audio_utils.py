"""Audio processing and text cleaning utilities for the voice subsystem."""

from __future__ import annotations

import io
import re
import wave


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

    # Convert dashes, ellipses, colons into natural comma pauses
    text = text.replace("...", ", ")
    text = text.replace("—", ", ")
    text = text.replace("–", ", ")
    text = text.replace(" - ", ", ")
    text = text.replace(" : ", ", ")

    # Expand common symbols to spoken words based on language/script
    is_bn = (language == "bn") or bool(re.search(r"[\u0980-\u09FF]", text))
    if is_bn:
        replacements = {
            "৳": " টাকা ",
            "%": " শতাংশ ",
            "$": " ডলার ",
            "&": " এবং ",
            "+": " যোগ ",
            "=": " সমান ",
            "/": " অথবা ",
            "°C": " ডিগ্রি সেলসিয়াস ",
            "°F": " ডিগ্রি ফারেনহাইট ",
        }
        # Expand common English tech terms in Bengali for smooth phonetics
        tech_bn = {
            r"\bAI\b": "এআই",
            r"\bAPI\b": "এপিআই",
            r"\bAPIs\b": "এপিআই",
            r"\bUI\b": "ইউআই",
            r"\bUX\b": "ইউএক্স",
            r"\bLLM\b": "এলএলএম",
            r"\bTTS\b": "টিটিএস",
            r"\bSTT\b": "এসটিটি",
        }
        for pattern, repl in tech_bn.items():
            text = re.sub(pattern, repl, text)
    else:
        replacements = {
            "%": " percent ",
            "$": " dollars ",
            "&": " and ",
            "+": " plus ",
            "=": " equals ",
            "/": " or ",
            "°C": " degrees Celsius ",
            "°F": " degrees Fahrenheit ",
            "℃": " degrees Celsius ",
            "℉": " degrees Fahrenheit ",
        }
    for char, word in replacements.items():
        text = text.replace(char, word)

    # Expand common technical and conversational abbreviations for natural pronunciation
    if not is_bn:
        # Punctuation-based abbreviations
        text = re.sub(r"\be\.g\.,?\b", "for example, ", text, flags=re.IGNORECASE)
        text = re.sub(r"\bi\.e\.,?\b", "that is, ", text, flags=re.IGNORECASE)
        text = re.sub(r"\bvs\.\b|\bvs\b", "versus", text, flags=re.IGNORECASE)
        text = re.sub(r"\betc\.\b|\betc\b", "etcetera", text, flags=re.IGNORECASE)
        text = re.sub(r"\bDr\.\b", "Doctor ", text)
        text = re.sub(r"\bMr\.\b", "Mister ", text)
        text = re.sub(r"\bMrs\.\b", "Missus ", text)
        text = re.sub(r"\bMs\.\b", "Miss ", text)

        # Technical acronyms to phonetic letters for smooth vocalization
        text = re.sub(r"\bAI\b", "A.I.", text)
        text = re.sub(r"\bAPI\b", "A.P.I.", text)
        text = re.sub(r"\bAPIs\b", "A.P.I.s", text)
        text = re.sub(r"\bUI\b", "U.I.", text)
        text = re.sub(r"\bUX\b", "U.X.", text)
        text = re.sub(r"\bURL\b", "U.R.L.", text)
        text = re.sub(r"\bURLs\b", "U.R.L.s", text)
        text = re.sub(r"\bLLM\b", "L.L.M.", text)
        text = re.sub(r"\bLLMs\b", "L.L.M.s", text)

    # Remove HTML tags and remaining brackets
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\[\]{}<>]", " ", text)

    # Remove Markdown headers and bold/italic markers
    text = re.sub(r"^#+\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_~`]", "", text)

    # Remove bullet symbols and number list prefixes
    text = re.sub(r"(?m)^\s*[-*+•]\s+", "", text)
    text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)

    # Remove stray non-speech punctuation (preserve Bengali danda \u0964 and double danda \u0965)
    text = re.sub(r"[|#\\^~]", " ", text)

    # Normalize whitespace and ensure natural comma spacing
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*\.\s*", ". ", text)
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
