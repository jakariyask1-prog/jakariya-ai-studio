"""High-quality Offline/Free Text-to-Speech provider using Edge TTS."""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import Future

from app.voice.business_logic.tts.tts_provider import TTSProvider


class EdgeNeuralTTS(TTSProvider):
    """TTSProvider implementation using Microsoft Edge TTS (Neural Voices).

    Uses edge-tts to generate ultra high-quality, natural-sounding neural voices
    that support Bengali and English. It uses miniaudio to decode the MP3 into PCM
    so the AudioPlayer can play it without ffmpeg.

    Performance: A single persistent SelectorEventLoop runs on a dedicated daemon
    thread and is reused for every synthesis call via run_coroutine_threadsafe().
    This eliminates the per-call asyncio startup overhead on Windows while avoiding
    ProactorEventLoop / aiohttp incompatibilities.
    """

    provider_id = "edge_neural_tts"
    display_name = "Edge Neural TTS (Free)"

    # ------------------------------------------------------------------ #
    # Class-level persistent event loop (shared across all instances)     #
    # ------------------------------------------------------------------ #
    _loop: asyncio.AbstractEventLoop | None = None
    _loop_thread: threading.Thread | None = None
    _loop_lock: threading.Lock = threading.Lock()

    @classmethod
    def _ensure_loop(cls) -> asyncio.AbstractEventLoop:
        """Return the shared persistent SelectorEventLoop, creating it once."""
        with cls._loop_lock:
            if cls._loop is not None and cls._loop.is_running():
                return cls._loop

            # Windows: force SelectorEventLoop so aiohttp / edge-tts works correctly.
            # ProactorEventLoop (the Windows default in Python 3.8+) is incompatible
            # with aiohttp's connector, which causes hangs.
            loop = asyncio.SelectorEventLoop()

            cls._loop = loop
            cls._loop_thread = threading.Thread(
                target=loop.run_forever,
                daemon=True,
                name="EdgeTTS-Loop",
            )
            cls._loop_thread.start()
            logging.debug("[EdgeNeuralTTS] Persistent SelectorEventLoop started on EdgeTTS-Loop thread")
            return loop

    def _run(self, coro) -> bytes:
        """Schedule *coro* on the persistent loop and wait for the result."""
        loop = self._ensure_loop()
        future: Future = asyncio.run_coroutine_threadsafe(coro, loop)
        # 25-second timeout guards against network hangs
        return future.result(timeout=25)

    # ------------------------------------------------------------------ #
    # Core synthesis                                                       #
    # ------------------------------------------------------------------ #

    async def _fetch_audio(self, text: str, voice: str, rate: str, pitch: str) -> bytes:
        """Stream MP3 chunks from edge-tts and return the complete MP3 bytes."""
        import edge_tts
        communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, volume="+0%")
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)

    def is_available(self) -> bool:
        """Return True since edge-tts doesn't require API keys."""
        return True

    def _resolve_voice(self, has_bengali: bool, language: str = "") -> str:
        """Resolve voice name, respecting user Settings or picking natural conversational defaults."""
        try:
            from app.settings.settings_manager import SettingsManager
            cfg_voice = SettingsManager.instance().service.schema.voice.voice_id
            if cfg_voice and cfg_voice.strip() and "Neural" in cfg_voice:
                if has_bengali:
                    if "bn-" in cfg_voice:
                        return cfg_voice.strip()
                else:
                    if not cfg_voice.startswith("bn-"):
                        return cfg_voice.strip()
        except Exception:
            pass

        # Most natural conversational defaults:
        # Bengali: bn-BD-NabanitaNeural (natural Bangladesh female)
        # English: en-US-JennyNeural (warm, expressive human conversational tone)
        return "bn-BD-NabanitaNeural" if has_bengali else "en-US-JennyNeural"

    def synthesise(self, text: str, language: str) -> bytes:
        """Convert text to raw PCM bytes (16kHz, 16-bit, mono) via edge-tts + miniaudio."""
        from app.voice.utils.audio_utils import strip_markdown

        clean_text = strip_markdown(text, language=language).strip()
        if not clean_text or not any(char.isalnum() for char in clean_text):
            return b""

        try:
            import miniaudio

            has_bengali = any("\u0980" <= ch <= "\u09ff" for ch in clean_text)
            voice = self._resolve_voice(has_bengali, language)
            rate, pitch = "+0%", "+0Hz"

            # Attempt synthesis with chosen voice; fallback on failure
            try:
                mp3_bytes = self._run(self._fetch_audio(clean_text, voice, rate, pitch))
            except Exception as primary_exc:
                logging.warning(
                    f"[EdgeNeuralTTS] Primary voice '{voice}' failed: {primary_exc} — trying fallback"
                )
                fallback = "en-US-JennyNeural" if voice != "en-US-JennyNeural" else "en-US-GuyNeural"
                mp3_bytes = self._run(self._fetch_audio(clean_text, fallback, rate, pitch))

            if not mp3_bytes:
                logging.warning(f"[EdgeNeuralTTS] No audio received for: {text[:60]!r}")
                return b""

            # Decode MP3 → raw PCM (16-bit, 16 kHz, mono) — no ffmpeg required
            decoded = miniaudio.decode(mp3_bytes, nchannels=1, sample_rate=16000)
            return decoded.samples.tobytes()

        except Exception as exc:
            msg = str(exc)
            if "No audio was received" in msg:
                logging.warning(f"[EdgeNeuralTTS] No audio for text: {text[:60]!r}")
                return b""
            logging.exception(f"[EdgeNeuralTTS] Synthesis failed for: {text[:60]!r}")
            raise RuntimeError(f"Edge Neural TTS synthesis failed: {exc}") from exc
