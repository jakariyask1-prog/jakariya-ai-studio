"""Asynchronous voice conversation pipeline orchestrating STT -> Claude -> TTS."""

from __future__ import annotations

from typing import Any
import re
import socket
import logging
from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.api.ClaudeClient import ClaudeClient
from app.voice.business_logic.pipeline.interruption import InterruptionToken
from app.voice.utils.audio_utils import strip_markdown
from app.voice.voice_service import VoiceService
from app.voice.voice_state import VoiceState


class PipelineWorker(QObject):
    """Background worker that executes STT -> Claude -> TTS on a dedicated thread."""

    state_changed = Signal(VoiceState)
    transcript_ready = Signal(str)
    response_started = Signal()
    partial_token = Signal(str)
    response_ready = Signal(str)
    audio_ready = Signal(bytes)
    error_occurred = Signal(str)
    turn_completed = Signal()
    stream_complete = Signal()  # Emitted when the last TTS chunk has been sent

    def __init__(self, service: VoiceService) -> None:
        super().__init__()
        self._service = service

    @Slot(bytes, object, object, bool, object, object)
    def process_turn(
        self,
        audio_bytes: bytes,
        history: list[dict[str, Any]] | None = None,
        token: InterruptionToken | None = None,
        is_live: bool = False,
        model: str | None = None,
        provider_id: str | None = None,
    ) -> None:
        """Execute one complete voice turn.

        Flow: Audio -> ElevenLabs STT -> Claude API -> ElevenLabs TTS -> Audio Output
        """
        try:
            if token and token.is_cancelled:
                return

            settings = self._service.settings

            # --- 1. STT Phase ---
            self.state_changed.emit(VoiceState.TRANSCRIBING)
            stt_provider = self._service.active_stt_provider()
            transcript = self._transcribe_with_fallback(stt_provider, audio_bytes, settings.language)

            if token and token.is_cancelled:
                return

            if not transcript.strip():
                self.turn_completed.emit()
                return

            clean_trans = re.sub(r'[^\w\s]', '', transcript).strip().lower()
            noise_artifacts = {"thank you", "you", "thanks for watching", "music", "blank_audio", "mbc", "amaraorg", "subtitles", "bye"}
            if not clean_trans or clean_trans in noise_artifacts or len(clean_trans) < 2:
                logging.debug(f"[PipelineWorker] Ignoring STT ambient noise artifact: '{transcript.strip()}'")
                self.turn_completed.emit()
                return

            self.transcript_ready.emit(transcript)

            # Pure STT Mode: Non-live microphone turns stop after STT transcription
            # to populate text into the prompt input box without auto-sending.
            if not is_live:
                self.turn_completed.emit()
                return

            # --- 2 & 3. Streaming Claude & TTS Phase ---
            self.state_changed.emit(VoiceState.THINKING)
            # Bug Fix #5: Create a fresh ClaudeClient per turn.
            # A shared/cached instance holds mutable state (_messages list, web flags)
            # that becomes corrupted if a new turn fires before the previous
            # generator is fully consumed (e.g. rapid-fire voice turns or barge-in).
            claude = ClaudeClient()

            ai_response_chunks: list[str] = []
            sentence_buffer = ""
            is_first_audio = True

            if settings.voice_response:
                tts_provider = self._service.active_tts_provider()

            # ----------------------------------------------------------------
            # Natural continuous speech flow & pre-roll/post-roll padding
            # ----------------------------------------------------------------
            # Pre-roll silence (120ms = 3840 zero bytes @ 16kHz 16-bit mono):
            #   Prepended to first TTS chunk so Windows QAudioSink / WASAPI
            #   hardware initializes during silence → zero first-word clipping.
            # Post-roll silence (250ms = 8000 zero bytes @ 16kHz 16-bit mono):
            #   Appended to final TTS chunk so hardware drains the last spoken
            #   syllable cleanly → zero last-word clipping.
            # ----------------------------------------------------------------
            # ----------------------------------------------------------------
            # Complete sentence-level speech synthesis
            # ----------------------------------------------------------------
            # Neural TTS models (like ElevenLabs eleven_multilingual_v2) need
            # complete sentence context to maintain a consistent speaker timbre,
            # natural prosody, and correct language pronunciation.
            # Splitting at commas or tiny word fragments causes multi-speaker
            # pitch artifacts and language confusion.
            # ----------------------------------------------------------------
            SENTENCE_END_RE = re.compile(r'([.!?\n\u0964\u0965]+(?:\s+|$))')
            FIRST_CHUNK_END_RE = re.compile(r'([.!?,，;:\n\u0964\u0965]+(?:\s+|$))')
            MAX_RUNON_WORD_TRIGGER = 14  # Safe threshold for unpunctuated run-on text

            LEADING_SILENCE = b"\x00" * 3840   # ~120ms leading silence (WASAPI hardware init)
            TRAILING_SILENCE = b"\x00" * 4800  # ~150ms trailing silence (avoids dead air gaps)

            def _emit_tts_chunk(text: str, is_first: bool) -> bool:
                nonlocal is_first_audio
                clean_text = strip_markdown(text, language=settings.language).strip()
                if not clean_text or not any(char.isalnum() for char in clean_text):
                    return False

                tts_audio = self._synthesise_with_fallback(tts_provider, clean_text, settings.language)
                if token and token.is_cancelled:
                    return False

                if tts_audio:
                    if is_first:
                        self.state_changed.emit(VoiceState.SPEAKING)
                        is_first_audio = False
                    audio_payload = (LEADING_SILENCE + tts_audio) if is_first else tts_audio
                    self.audio_ready.emit(audio_payload)
                    return True
                return False

            is_first_token = True
            for chunk in claude.ask_stream(transcript, model=model, history=history, provider_id=provider_id, is_live=is_live):
                if token and token.is_cancelled:
                    return
                if is_first_token:
                    self.response_started.emit()
                    is_first_token = False
                self.partial_token.emit(chunk)
                ai_response_chunks.append(chunk)

                if not settings.voice_response:
                    continue

                sentence_buffer += chunk

                if is_first_audio:
                    # Snappy first-token playback: Trigger on first clause/comma or after 5+ words
                    match = FIRST_CHUNK_END_RE.search(sentence_buffer)
                    if match:
                        cand = sentence_buffer[:match.end()]
                        cand_words = cand.split()
                        if len(cand_words) >= 2 or len(cand.strip()) >= 8:
                            sentence_buffer = sentence_buffer[match.end():]
                            _emit_tts_chunk(cand, is_first=True)
                    elif len(sentence_buffer.split()) >= 6:
                        last_space = sentence_buffer.rfind(" ")
                        if last_space > 0:
                            cand = sentence_buffer[:last_space + 1]
                            if _emit_tts_chunk(cand, is_first=True):
                                sentence_buffer = sentence_buffer[last_space + 1:]
                else:
                    # --- Complete sentence boundary (. ! ? Bengali dandas \n) ---
                    match = SENTENCE_END_RE.search(sentence_buffer)
                    while match:
                        split_idx = match.end()
                        sentence = sentence_buffer[:split_idx]
                        sentence_buffer = sentence_buffer[split_idx:]
                        _emit_tts_chunk(sentence, is_first=False)
                        match = SENTENCE_END_RE.search(sentence_buffer)

                    # --- Safety split for long unpunctuated run-on sentences ---
                    words_in_buf = sentence_buffer.split()
                    if len(words_in_buf) >= MAX_RUNON_WORD_TRIGGER:
                        last_space = sentence_buffer.rfind(" ")
                        if last_space > 0:
                            split_idx = last_space + 1
                            sentence = sentence_buffer[:split_idx]
                            if _emit_tts_chunk(sentence, is_first=False):
                                sentence_buffer = sentence_buffer[split_idx:]

            ai_response = "".join(ai_response_chunks)
            if token and token.is_cancelled:
                return

            self.response_ready.emit(ai_response)

            # Flush remaining buffer for final TTS chunk (with trailing silence for zero last-word clipping)
            if settings.voice_response and sentence_buffer.strip():
                clean_text = strip_markdown(sentence_buffer, language=settings.language).strip()
                if clean_text:
                    tts_audio = self._synthesise_with_fallback(tts_provider, clean_text, settings.language)
                    if not (token and token.is_cancelled) and tts_audio:
                        if is_first_audio:
                            self.state_changed.emit(VoiceState.SPEAKING)
                            is_first_audio = False
                            self.audio_ready.emit(LEADING_SILENCE + tts_audio + TRAILING_SILENCE)
                        else:
                            self.audio_ready.emit(tts_audio + TRAILING_SILENCE)
            elif settings.voice_response and not is_first_audio:
                # Buffer was empty at end, but previous audio chunks were sent. Send trailing silence to flush hardware.
                if not (token and token.is_cancelled):
                    self.audio_ready.emit(TRAILING_SILENCE)

            if not (token and token.is_cancelled):
                # Always emit stream_complete so AudioPlayer.mark_complete() is called exactly once.
                # When voice_response=False no audio was sent, mark_complete() immediately
                # emits playback_finished so Live Mode can restart listening cleanly.
                self.stream_complete.emit()
                self.turn_completed.emit()

        except Exception as error:
            if not (token and token.is_cancelled):
                logging.exception("Pipeline processing error")
                error_msg = str(error)
                error_msg_lower = error_msg.lower()
                if "rate-limited" in error_msg_lower or "rate limit" in error_msg_lower or "429" in error_msg_lower:
                    self.error_occurred.emit(
                        f"Model rate-limited: {error_msg}. Please select another model from the header dropdown."
                    )
                elif isinstance(error, (TimeoutError, socket.timeout)) or "timeout" in error_msg_lower:
                    self.error_occurred.emit("Connection timed out. Please check your network and try again.")
                else:
                    self.error_occurred.emit(error_msg)
                self.turn_completed.emit()

    def _transcribe_with_fallback(self, stt_provider, audio_bytes: bytes, language: str) -> str:
        """Transcribe audio using primary STT provider with automatic fallbacks (Groq -> Google STT)."""
        if not audio_bytes:
            return ""

        try:
            res = stt_provider.transcribe(audio_bytes, language)
            if res:
                return res
        except Exception as exc:
            pid = getattr(stt_provider, "provider_id", "primary")
            logging.warning(
                f"[PipelineWorker] Primary STT provider '{pid}' failed ({exc}). Trying fallbacks..."
            )

        # Fallback 1: Groq STT (if primary wasn't groq_stt)
        if getattr(stt_provider, "provider_id", "") != "groq_stt":
            try:
                fallback_groq = self._service.get_stt_provider("groq_stt")
                if fallback_groq and fallback_groq.is_available():
                    res = fallback_groq.transcribe(audio_bytes, language)
                    if res:
                        return res
            except Exception as exc:
                logging.warning(f"[PipelineWorker] Fallback Groq STT failed: {exc}")

        # Fallback 2: Free Google STT
        if getattr(stt_provider, "provider_id", "") != "google_stt":
            try:
                fallback = self._service.get_stt_provider("google_stt")
                if fallback and fallback.is_available():
                    return fallback.transcribe(audio_bytes, language)
            except Exception as exc:
                logging.exception(f"[PipelineWorker] Fallback Google STT failed: {exc}")

        return ""

    def _synthesise_with_fallback(self, tts_provider, text: str, language: str) -> bytes:
        """Synthesise text using primary TTS provider with fallbacks to Edge Neural TTS and Google TTS."""
        clean_text = strip_markdown(text, language=language).strip()
        if not clean_text or not any(char.isalnum() for char in clean_text):
            return b""

        # Try primary TTS provider first
        try:
            audio = tts_provider.synthesise(clean_text, language)
            if audio:
                return audio
        except Exception as exc:
            logging.warning(
                f"[PipelineWorker] Primary TTS provider '{getattr(tts_provider, 'provider_id', 'unknown')}' "
                f"failed ({exc}). Trying fallbacks..."
            )

        # Fallback 1: Edge Neural TTS (if primary wasn't edge_neural_tts)
        if getattr(tts_provider, "provider_id", "") != "edge_neural_tts":
            try:
                fallback = self._service.get_tts_provider("edge_neural_tts")
                if fallback and fallback.is_available():
                    audio = fallback.synthesise(clean_text, language)
                    if audio:
                        return audio
            except Exception as exc:
                logging.exception(f"[PipelineWorker] Fallback Edge Neural TTS failed: {exc}")

        # Fallback 2: Google TTS (gTTS)
        try:
            fallback_gtts = self._service.get_tts_provider("google_tts")
            if fallback_gtts and fallback_gtts.is_available():
                audio = fallback_gtts.synthesise(clean_text, language)
                if audio:
                    return audio
        except Exception as exc:
            logging.exception(f"[PipelineWorker] Fallback Google TTS (gTTS) failed: {exc}")

        return b""


class ConversationPipeline(QObject):
    """Thread manager and event bridge for the voice conversation pipeline."""

    state_changed = Signal(VoiceState)
    transcript_ready = Signal(str)
    response_started = Signal()
    partial_token = Signal(str)
    response_ready = Signal(str)
    audio_ready = Signal(bytes)
    error_occurred = Signal(str)
    turn_completed = Signal()
    stream_complete = Signal()  # Forwarded from worker

    _request_turn_signal = Signal(bytes, object, object, bool, object, object)

    def __init__(self, service: VoiceService) -> None:
        super().__init__()
        self._service = service
        self._thread = QThread()
        self._worker = PipelineWorker(service)
        self._worker.moveToThread(self._thread)

        # Relay worker signals
        self._worker.state_changed.connect(self.state_changed.emit)
        self._worker.transcript_ready.connect(self.transcript_ready.emit)
        self._worker.response_started.connect(self.response_started.emit)
        self._worker.partial_token.connect(self.partial_token.emit)
        self._worker.response_ready.connect(self.response_ready.emit)
        self._worker.audio_ready.connect(self.audio_ready.emit)
        self._worker.error_occurred.connect(self.error_occurred.emit)
        self._worker.turn_completed.connect(self.turn_completed.emit)
        self._worker.stream_complete.connect(self.stream_complete.emit)

        self._request_turn_signal.connect(self._worker.process_turn)
        self._thread.start()

    def run_turn(
        self,
        audio_bytes: bytes,
        history: list[dict[str, Any]] | None = None,
        token: InterruptionToken | None = None,
        is_live: bool = False,
        model: str | None = None,
        provider_id: str | None = None,
    ) -> None:
        """Dispatch a voice turn to the background pipeline worker."""
        self._request_turn_signal.emit(audio_bytes, history, token, is_live, model, provider_id)

    def shutdown(self) -> None:
        """Safely terminate the pipeline worker thread."""
        if hasattr(self, "_thread") and self._thread and self._thread.isRunning():
            try:
                self._request_turn_signal.disconnect()
            except Exception:
                pass
            self._thread.quit()
            if not self._thread.wait(2000):
                self._thread.terminate()
                self._thread.wait()
            if hasattr(self, "_worker") and self._worker:
                try:
                    self._worker.deleteLater()
                except Exception:
                    pass

    def __del__(self) -> None:
        try:
            self.shutdown()
        except Exception:
            pass
