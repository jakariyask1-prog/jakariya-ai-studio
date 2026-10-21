"""Google Web Speech API STT provider."""

from __future__ import annotations

import io
import re
import logging
import warnings
from concurrent.futures import ThreadPoolExecutor

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import speech_recognition as sr

from app.voice.business_logic.stt.stt_provider import STTProvider
from app.voice.utils.patch_speech import patch_speech_recognition

# Ensure speech_recognition FLAC converter is patched in windowed and frozen modes
patch_speech_recognition()

logger = logging.getLogger(__name__)

# Common English vocabulary used to distinguish genuine English speech from
# phonetic Banglish transliterations returned by the English speech recognition model.
_COMMON_ENGLISH_WORDS = frozenset({
    # Basic pronouns, determiners & question words
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "us", "them", "who", "whom", "whose", "which", "what",
    "how", "why", "when", "where", "if", "whether", "as", "because", "and", "but", "or", "nor", "so", "yet",
    # Common verbs & auxiliaries
    "is", "am", "are", "was", "were", "be", "being", "been", "have", "has", "had", "having",
    "do", "does", "did", "doing", "done", "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "say", "says", "said", "go", "goes", "went", "going", "gone", "come", "comes", "came", "coming",
    "make", "makes", "made", "take", "takes", "took", "taken", "get", "gets", "got", "getting",
    "give", "gives", "gave", "given", "find", "finds", "found", "think", "thinks", "thought",
    "know", "knows", "knew", "known", "see", "sees", "saw", "seen", "look", "looks", "looked",
    "use", "uses", "used", "tell", "tells", "told", "ask", "asks", "asked", "asking",
    "work", "works", "worked", "call", "calls", "called", "try", "tries", "tried",
    "need", "needs", "needed", "feel", "feels", "felt", "become", "becomes", "became",
    "leave", "leaves", "left", "put", "puts", "mean", "means", "meant", "keep", "keeps", "kept",
    "let", "lets", "begin", "begins", "began", "seem", "seems", "seemed", "help", "helps", "helped",
    "talk", "talks", "talked", "turn", "turns", "turned", "start", "starts", "started",
    "show", "shows", "showed", "shown", "hear", "hears", "heard", "hearing", "play", "plays", "played",
    "run", "runs", "ran", "move", "moves", "moved", "like", "likes", "liked", "live", "lives", "lived",
    "believe", "believes", "believed", "hold", "holds", "held", "bring", "brings", "brought",
    "happen", "happens", "happened", "write", "writes", "wrote", "written", "writing",
    "provide", "provides", "sit", "sits", "sat", "stand", "stands", "stood", "lose", "loses", "lost",
    "pay", "pays", "paid", "meet", "meets", "met", "include", "includes", "included",
    "continue", "continues", "set", "sets", "setting", "learn", "learns", "learned",
    "change", "changes", "changed", "lead", "leads", "led", "understand", "understands", "understood",
    "watch", "watches", "watched", "follow", "follows", "followed", "stop", "stops", "stopped",
    "create", "creates", "created", "speak", "speaks", "spoke", "spoken", "read", "reads",
    "spend", "spends", "spent", "grow", "grows", "grew", "open", "opens", "opened",
    "walk", "walks", "walked", "win", "wins", "won", "teach", "teaches", "taught",
    "offer", "offers", "offered", "remember", "remembers", "remembered", "consider", "considers",
    "appear", "appears", "appeared", "buy", "buys", "bought", "serve", "serves", "served",
    "die", "dies", "died", "send", "sends", "sent", "build", "builds", "built",
    "stay", "stays", "stayed", "fall", "falls", "fell", "cut", "cuts", "reach", "reaches",
    "spell", "spelled", "spelling", "pronounce", "pronunciation", "meaning", "definition",
    # Prepositions & conjunctions
    "for", "at", "by", "from", "in", "into", "of", "off", "on", "onto", "out", "over", "to", "up",
    "with", "about", "above", "across", "after", "against", "along", "among", "around", "before",
    "behind", "below", "beside", "between", "beyond", "down", "during", "except", "inside", "near",
    "since", "through", "throughout", "toward", "towards", "under", "until", "upon", "without",
    # Common adjectives & adverbs
    "good", "new", "first", "last", "long", "great", "little", "own", "other", "old", "right", "big", "high",
    "different", "small", "large", "next", "early", "young", "important", "few", "public", "bad", "same", "able",
    "up", "so", "out", "just", "now", "then", "more", "also", "here", "well", "only", "very", "even",
    "back", "there", "down", "still", "too", "never", "really", "most", "again", "always", "today",
    "tomorrow", "yesterday", "tonight", "soon", "fast", "slow", "correct", "wrong", "true", "false",
    "sure", "nice", "fine", "better", "best", "simple", "complex", "easy", "hard", "clear", "clean",
    # Nouns & common tech terms
    "time", "year", "people", "way", "day", "man", "thing", "woman", "life", "child", "world", "school", "state",
    "family", "student", "group", "country", "problem", "hand", "part", "place", "case", "week", "company", "system",
    "program", "programming", "question", "government", "number", "night", "point", "home", "water", "room",
    "mother", "area", "money", "story", "fact", "month", "lot", "study", "book", "eye", "job", "word", "words",
    "business", "issue", "side", "kind", "head", "house", "service", "friend", "father", "power", "hour", "game",
    "line", "end", "member", "law", "car", "city", "community", "name", "president", "capital", "france", "england",
    "america", "bangladesh", "dhaka", "paris", "london", "weather", "forecast", "cloud", "rain", "temperature",
    "code", "coding", "python", "script", "function", "variable", "class", "file", "folder", "project", "app",
    "application", "website", "web", "browser", "model", "ai", "artificial", "intelligence", "studio", "assistant",
    "voice", "speech", "text", "audio", "sound", "microphone", "speaker", "phone", "computer", "screen", "keyboard",
    "error", "bug", "fix", "test", "testing", "button", "window", "data", "database", "query", "search",
    "internet", "online", "chat", "message", "response", "answer", "input", "output", "image", "document",
    "psychological", "science", "history", "geography", "math", "mathematics", "english", "bengali", "bangla",
    "please", "thank", "thanks", "welcome", "hello", "hi", "hey", "bye", "goodbye", "morning", "afternoon", "evening"
})

_BANGLISH_MARKERS = frozenset({
    "ajker", "abohar", "kemon", "tumi", "ami", "apni", "bhalo", "ekta", "ekti", "likhe",
    "banega", "korun", "koro", "ache", "nai", "amake", "tomake", "apnake", "shobar", "shobai",
    "shokal", "shondha", "raat", "bhaat", "khabar", "desh", "desher", "shundor", "shob"
})


class GoogleSTT(STTProvider):
    """STTProvider implementation using Google Web Speech API.

    Features intelligent dual-language detection for Bengali (bn-BD) and
    English (en-US) when language is set to 'auto', preventing phonetic
    character corruption and misrecognized spellings.
    """

    provider_id = "google_stt"
    display_name = "Google STT (Free)"

    def is_available(self) -> bool:
        """Return True since this uses the free Google API."""
        return True

    def _recognize_single(self, audio_bytes: bytes, lang_code: str) -> str:
        """Run standard single-locale Google Web Speech transcription."""
        wav_io = io.BytesIO(audio_bytes)
        rec = sr.Recognizer()
        with sr.AudioFile(wav_io) as source:
            audio_data = rec.record(source)
        return rec.recognize_google(audio_data, language=lang_code).strip()

    def _choose_best_auto_transcript(self, text_bn: str | None, text_en: str | None) -> str:
        """Intelligently select between Bengali and English transcriptions.

        Prevents English speech from being transliterated into Bengali phonetics
        (e.g., 'Hello, how are you' -> 'হ্যালো হাউ আর ইউ') while maintaining 100%
        accurate Bengali script when Bengali is spoken.
        """
        if not text_bn and not text_en:
            return ""
        if not text_bn:
            return (text_en or "").strip()
        if not text_en:
            return text_bn.strip()

        clean_bn = text_bn.strip()
        clean_en = text_en.strip()

        # Tokenize English candidate words
        en_words = [w.lower() for w in re.findall(r"[a-zA-Z]+", clean_en)]
        if not en_words:
            return clean_bn

        # Calculate proportion of known English words
        known_count = sum(1 for w in en_words if w in _COMMON_ENGLISH_WORDS)
        match_ratio = known_count / len(en_words)

        # Detect phonetic Banglish markers in English transcription
        has_banglish = any(w in _BANGLISH_MARKERS for w in en_words)

        # If English output is predominantly genuine English and free of Banglish markers,
        # the speaker spoke English -> return English text with correct spelling.
        if match_ratio >= 0.5 and not has_banglish:
            return clean_en

        # Otherwise, the speaker spoke Bengali or Banglish -> return native Bengali script.
        return clean_bn

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        """Transcribe WAV audio bytes to text using Google's Web Speech API.

        When language is 'auto', queries both 'bn-BD' and 'en-US' concurrently
        and intelligently selects the authentic language candidate.
        """
        if not audio_bytes:
            return ""

        lang_code = language.strip().lower() if language else "auto"

        # Explicit Bengali request
        if lang_code in ("bn", "bn-bd", "bangla", "bengali"):
            try:
                return self._recognize_single(audio_bytes, "bn-BD")
            except sr.UnknownValueError:
                return ""
            except Exception as exc:
                logger.exception("Failed to transcribe Bengali audio via Google STT")
                raise RuntimeError(f"Google STT processing failed: {exc}") from exc

        # Explicit English request
        if lang_code in ("en", "en-us", "en-gb", "english"):
            try:
                return self._recognize_single(audio_bytes, "en-US")
            except sr.UnknownValueError:
                return ""
            except Exception as exc:
                logger.exception("Failed to transcribe English audio via Google STT")
                raise RuntimeError(f"Google STT processing failed: {exc}") from exc

        # Explicit other language (e.g. 'hi-IN', 'fr-FR', etc.)
        if lang_code not in ("auto", "all", ""):
            try:
                return self._recognize_single(audio_bytes, language)
            except sr.UnknownValueError:
                return ""
            except Exception as exc:
                logger.exception("Failed to transcribe audio via Google STT")
                raise RuntimeError(f"Google STT processing failed: {exc}") from exc

        # Intelligent Dual-Language Auto-Detection ('auto')
        # Concurrently queries bn-BD and en-US in parallel for lowest latency (~350ms)
        def _fetch_bn() -> str | None:
            try:
                return self._recognize_single(audio_bytes, "bn-BD")
            except Exception:
                return None

        def _fetch_en() -> str | None:
            try:
                return self._recognize_single(audio_bytes, "en-US")
            except Exception:
                return None

        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                future_bn = executor.submit(_fetch_bn)
                future_en = executor.submit(_fetch_en)
                res_bn = future_bn.result()
                res_en = future_en.result()

            selected = self._choose_best_auto_transcript(res_bn, res_en)
            return selected

        except Exception as exc:
            logger.exception("Failed to transcribe audio via Google STT dual-language pipeline")
            raise RuntimeError(f"Google STT processing failed: {exc}") from exc

