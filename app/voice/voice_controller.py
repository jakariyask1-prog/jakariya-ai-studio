"""Qt controller bridging the GUI, Audio Engine, and Conversation Pipeline.

:class:`VoiceController` manages microphone recording, handles state transitions
via :class:`VoiceManager`, and runs non-blocking STT -> Claude -> TTS execution
via :class:`ConversationPipeline`.
"""

from __future__ import annotations

from typing import Any
import logging
import time
from PySide6.QtCore import QObject, Signal, QTimer

from app.voice.business_logic.audio.audio_player import AudioPlayer
from app.voice.business_logic.audio.microphone import MicrophoneManager
from app.voice.business_logic.pipeline.conversation_pipeline import ConversationPipeline
from app.voice.business_logic.pipeline.interruption import InterruptionToken
from app.voice.voice_manager import VoiceManager
from app.voice.voice_settings import VoiceSettings
from app.voice.voice_state import VoiceState


class VoiceController(QObject):
    """Bridge between Qt GUI, audio devices, and background voice pipeline.

    Responsibilities
    ----------------
    * Control microphone capture start/stop.
    * Route captured WAV audio into :class:`ConversationPipeline`.
    * Track pipeline state transitions and notify GUI via signals.
    * Support turn cancellation/interruption & barge-in.
    """

    state_changed = Signal(VoiceState)
    transcript_ready = Signal(str)
    response_started = Signal()
    partial_token = Signal(str)
    response_ready = Signal(str)
    audio_ready = Signal(bytes)
    error_occurred = Signal(str)

    def __init__(
        self,
        manager: VoiceManager,
        microphone_manager: MicrophoneManager | None = None,
        audio_player: AudioPlayer | None = None,
        pipeline: ConversationPipeline | None = None,
    ) -> None:
        super().__init__()
        self._manager = manager
        self._mic_manager = microphone_manager or MicrophoneManager(self)
        self._player = audio_player or AudioPlayer(self)
        self._pipeline = pipeline or ConversationPipeline(manager.service)
        self._active_interruption_token: InterruptionToken | None = None
        self._running_turn_token: InterruptionToken | None = None
        self._is_shutting_down: bool = False
        self._turn_start_time: float = 0.0
        self._restart_scheduled: bool = False  # Guard: prevents double _maybe_restart_listening calls
        self._history_provider = None  # Callable[[], list] that fetches conversation history
        self._model_provider = None  # Callable[[], str] that returns selected model ID
        self._provider_id_provider = None  # Callable[[], str] that returns selected provider ID

        # Wire pipeline signals
        self._pipeline.state_changed.connect(self._on_pipeline_state_changed)
        self._pipeline.transcript_ready.connect(self.transcript_ready.emit)
        self._pipeline.response_started.connect(self.response_started.emit)
        self._pipeline.partial_token.connect(self.partial_token.emit)
        self._pipeline.response_ready.connect(self.response_ready.emit)
        self._pipeline.audio_ready.connect(self.audio_ready.emit)
        self._pipeline.error_occurred.connect(self._on_pipeline_error)
        self._pipeline.turn_completed.connect(self._on_pipeline_turn_completed)
        self._pipeline.stream_complete.connect(self._player.mark_complete)

        # Wire audio player signals
        self._player.playback_finished.connect(self._on_playback_finished)
        
        # Wire microphone signals
        self._mic_manager.silence_detected.connect(self._on_silence_detected)
        self._mic_manager.speech_started.connect(self._on_speech_started)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> VoiceState:
        """Return the current pipeline state."""
        return self._manager.state

    @property
    def settings(self) -> VoiceSettings:
        """Return the active voice settings."""
        return self._manager.settings

    @property
    def mic_manager(self) -> MicrophoneManager:
        """Return the microphone manager instance."""
        return self._mic_manager

    @property
    def player(self) -> AudioPlayer:
        """Return the audio player instance."""
        return self._player

    def update_settings(self, settings: VoiceSettings) -> None:
        """Apply updated settings to the manager and sync VAD params to microphone."""
        self._manager.update_settings(settings)
        # Propagate VAD / silence settings into MicrophoneManager
        if hasattr(settings, 'silence_timeout_ms'):
            self._mic_manager.silence_timeout_ms = settings.silence_timeout_ms
        if hasattr(settings, 'vad_threshold'):
            self._mic_manager.vad_threshold = settings.vad_threshold

    def set_history_provider(self, provider) -> None:
        """Register a callable that returns current conversation history for live mode."""
        self._history_provider = provider

    def set_model_provider(self, provider) -> None:
        """Register a callable that returns the selected model ID for voice turns."""
        self._model_provider = provider

    def set_provider_id_provider(self, provider) -> None:
        """Register a callable that returns the selected provider ID for voice turns."""
        self._provider_id_provider = provider

    def can_start(self) -> bool:
        """Return ``True`` when a new voice turn can begin."""
        return self._manager.can_start()

    def start_listening(self) -> None:
        """Open the microphone and begin audio capture."""
        if self._manager.state in (VoiceState.SPEAKING, VoiceState.THINKING, VoiceState.TRANSCRIBING):
            self.interrupt()
            self.reset()
        elif self._manager.state in (VoiceState.ERROR, VoiceState.INTERRUPTED):
            self.reset()

        if not self._manager.can_start():
            logging.debug(f"[VoiceController] start_listening blocked: state={self._manager.state}")
            return

        self._mic_manager.barge_in_monitoring = False
        self._mic_manager.set_gain(1.0)
        self._mic_manager.is_capturing = True
        self._active_interruption_token = InterruptionToken()
        success = self._mic_manager.start_recording()

        if success:
            self._manager.on_listening_started()
            self.state_changed.emit(self._manager.state)
            logging.debug("[VoiceController] start_listening: microphone actively recording")
        else:
            self._manager.on_error()
            self.error_occurred.emit("Failed to initialize microphone recording.")

    def stop_listening(self, history: list[dict[str, Any]] | None = None) -> None:
        """Stop microphone recording and trigger STT -> LLM -> TTS pipeline."""
        if self._manager.state != VoiceState.LISTENING:
            return

        self._mic_manager.is_capturing = False
        self._mic_manager.barge_in_monitoring = False

        if self.is_live_session_active():
            wav_bytes = self._mic_manager.get_wav_and_clear()
        else:
            wav_bytes = self._mic_manager.stop_recording()

        # Bug Fix #4: A WAV with only its 44-byte header (no real PCM data)
        # is truthy but contains no speech. Sending it to STT produces noise
        # artifacts and spurious LLM requests. Require at least ~200ms of audio
        # (44 header + 6400 bytes = 200ms at 16kHz 16-bit mono).
        MIN_REAL_AUDIO_BYTES = 44 + 6400  # 44-byte WAV header + ~200ms of PCM
        if not wav_bytes or len(wav_bytes) < MIN_REAL_AUDIO_BYTES:
            logging.debug(
                f"[VoiceController] stop_listening: discarding near-empty WAV "
                f"({len(wav_bytes) if wav_bytes else 0} bytes < {MIN_REAL_AUDIO_BYTES} required)"
            )
            if self.is_live_session_active():
                # Reset to READY and restart listening without going through error state
                self._manager.reset()
                self.state_changed.emit(self._manager.state)
                QTimer.singleShot(300, self.start_listening)
            else:
                self._manager.on_error()
                self.error_occurred.emit("No audio captured from microphone.")
            return

        self._turn_start_time = time.time()
        self._manager.on_transcribing_started()
        if self.is_live_session_active():
            self._mic_manager.set_gain(0.15)
        self.state_changed.emit(self._manager.state)

        model = None
        if self._model_provider is not None:
            try:
                model = self._model_provider()
            except Exception as model_err:
                logging.warning(f"[VoiceController] Failed to resolve model from provider: {model_err}")

        provider_id = None
        if self._provider_id_provider is not None:
            try:
                provider_id = self._provider_id_provider()
            except Exception as prov_err:
                logging.warning(f"[VoiceController] Failed to resolve provider_id from provider: {prov_err}")

        self._running_turn_token = self._active_interruption_token

        # Dispatch turn to pipeline
        self._pipeline.run_turn(
            audio_bytes=wav_bytes,
            history=history,
            token=self._active_interruption_token,
            is_live=self.is_live_session_active(),
            model=model,
            provider_id=provider_id,
        )

    def interrupt(self) -> None:
        """Cancel the active voice turn immediately."""
        logging.debug("[VoiceController] interrupt called")
        # Bug Fix #1 (partial): Clear restart guard so interrupted turns can restart cleanly
        self._restart_scheduled = False
        self._mic_manager.barge_in_monitoring = False
        self._mic_manager.is_capturing = False

        if self._active_interruption_token:
            self._active_interruption_token.cancel()

        if self._mic_manager.is_recording:
            if self.is_live_session_active() and not self._is_shutting_down:
                # Bug Fix #2: get_wav_and_clear() stops silence timer and resets VAD,
                # then restore gain to 1.0 so next listening turn captures at full volume.
                self._mic_manager.get_wav_and_clear()
                self._mic_manager.set_gain(1.0)
            else:
                self._mic_manager.stop_recording()

        if not self._manager.is_idle:
            self._manager.on_interrupted()
            self.state_changed.emit(self._manager.state)

        if self._player.is_playing:
            self._player.stop()

    def reset(self) -> None:
        """Reset state machine back to READY."""
        self._active_interruption_token = None
        self._running_turn_token = None
        self._manager.reset()
        self.state_changed.emit(self._manager.state)

    # ------------------------------------------------------------------
    # Live Session Controller
    # ------------------------------------------------------------------

    def start_live_session(self) -> None:
        """Start a continuous live voice session."""
        logging.debug("[VoiceController] start_live_session called")
        self.reset()
        self._manager.start_live_session()
        # In Live conversational mode, use low-latency silence timeout (550ms)
        # for ultra-fast, snappy conversational turn-taking
        self._mic_manager.silence_timeout_ms = 550
        self.start_listening()

    def stop_live_session(self) -> None:
        """Stop an active continuous live voice session."""
        logging.debug("[VoiceController] stop_live_session called")
        self._restart_scheduled = False
        self.interrupt()
        self._manager.stop_live_session()
        # Restore standard configured silence timeout
        if hasattr(self.settings, 'silence_timeout_ms'):
            self._mic_manager.silence_timeout_ms = self.settings.silence_timeout_ms
        self.state_changed.emit(self._manager.state)

    def is_live_session_active(self) -> bool:
        """Return ``True`` if a continuous live session is running."""
        return self._manager.is_live_session_active()

    def _maybe_restart_listening(self) -> None:
        """Check prerequisites and queue a new listening turn in Live Mode."""
        logging.debug(
            f"[VoiceController] _maybe_restart_listening check: live={self.is_live_session_active()} "
            f"state={self._manager.state} shutting_down={self._is_shutting_down}"
        )
        if not self.is_live_session_active():
            logging.debug("[VoiceController] _maybe_restart_listening: ABORT — live session not active")
            self._restart_scheduled = False
            return
        if self._is_shutting_down:
            logging.debug("[VoiceController] _maybe_restart_listening: ABORT — shutting down")
            self._restart_scheduled = False
            return
        if self._player.is_playing:
            logging.debug("[VoiceController] _maybe_restart_listening: ABORT — player still active")
            self._restart_scheduled = False
            return

        # Always reset state to READY and clear stale turn tokens before starting next turn in live session
        self.reset()

        logging.debug("[VoiceController] _maybe_restart_listening: scheduling start_listening in 40ms")
        QTimer.singleShot(40, self._do_restart_listening)

    def _do_restart_listening(self) -> None:
        """Actual deferred restart — clears guard flag then starts listening."""
        self._restart_scheduled = False
        if self.is_live_session_active() and not self._is_shutting_down:
            self._mic_manager.get_wav_and_clear()
            self._mic_manager.set_gain(1.0)
            self._mic_manager.is_capturing = True
            self.start_listening()

    def _restart_live_after_error(self) -> None:
        """Recover from an error during Live Mode."""
        self._restart_scheduled = False
        if self.is_live_session_active() and not self._is_shutting_down:
            if self._mic_manager.is_recording or self._manager.state == VoiceState.LISTENING:
                logging.debug("[VoiceController] Live Mode already recording — skipping duplicate error restart")
                return
            logging.debug("[VoiceController] Recovering Live Mode after error...")
            self.reset()
            self._mic_manager.get_wav_and_clear()
            self._mic_manager.set_gain(1.0)
            self._mic_manager.is_capturing = True
            self.start_listening()

    def shutdown(self) -> None:
        """Release audio resources and stop pipeline thread."""
        self._is_shutting_down = True
        self.interrupt()
        self._pipeline.shutdown()

    # ------------------------------------------------------------------
    # Internal Slots / Callbacks
    # ------------------------------------------------------------------

    def _enable_barge_in_monitoring(self) -> None:
        """Enable conservative barge-in detection after audio playback onset stabilization."""
        if self._manager.state == VoiceState.SPEAKING:
            self._mic_manager.barge_in_monitoring = True

    def _on_speech_started(self) -> None:
        """Handle user speech detection during AI playback (Barge-in)."""
        if self._manager.state == VoiceState.SPEAKING:
            logging.info("[VoiceController] Genuine barge-in detected! User spoke while AI was speaking. Interrupting...")
            self.interrupt()
            if self.is_live_session_active() and not self._restart_scheduled:
                self._restart_scheduled = True
                self.reset()
                QTimer.singleShot(40, self._do_restart_listening)

    def _on_pipeline_state_changed(self, new_state: VoiceState) -> None:
        if not self.is_live_session_active():
            if self._active_interruption_token and self._active_interruption_token.is_cancelled:
                return

        if new_state == VoiceState.TRANSCRIBING:
            self._manager.on_transcribing_started()
            self._mic_manager.is_capturing = False
            self._mic_manager.barge_in_monitoring = False
            if self.is_live_session_active():
                self._mic_manager.set_gain(0.15)
        elif new_state == VoiceState.THINKING:
            self._manager.on_thinking_started()
            self._mic_manager.is_capturing = False
            self._mic_manager.barge_in_monitoring = False
            if self.is_live_session_active():
                self._mic_manager.set_gain(0.15)
        elif new_state == VoiceState.SPEAKING:
            self._manager.on_speaking_started()
            self._mic_manager.is_capturing = False
            self._mic_manager.barge_in_monitoring = False
            if self.is_live_session_active():
                self._mic_manager.set_gain(0.15)
                # Wait 800ms before allowing barge-in monitoring to prevent speaker onset click
                QTimer.singleShot(800, self._enable_barge_in_monitoring)

        self.state_changed.emit(self._manager.state)

    def _on_pipeline_error(self, error_msg: str) -> None:
        if not self.is_live_session_active():
            if self._active_interruption_token and self._active_interruption_token.is_cancelled:
                return

        self._manager.on_error()
        self.state_changed.emit(self._manager.state)
        self.error_occurred.emit(error_msg)

        if self.is_live_session_active() and not self._restart_scheduled:
            self._restart_scheduled = True
            logging.debug("[VoiceController] Error occurred in Live Mode — auto-recovering in 1.5s")
            QTimer.singleShot(1500, self._restart_live_after_error)

    def _on_pipeline_turn_completed(self) -> None:
        logging.debug(f"[VoiceController] _on_pipeline_turn_completed: is_playing={self._player.is_playing} state={self._manager.state}")
        # Note: mark_complete() is already called via stream_complete signal wired in __init__.
        # Do NOT call it again here — double-calling causes a race where the drain
        # check fires before all audio chunks are written to the QAudioSink ring buffer.

        if not self.is_live_session_active():
            if self._active_interruption_token and self._active_interruption_token.is_cancelled:
                return
            if self._running_turn_token and self._running_turn_token.is_cancelled:
                return

            if self._manager.state not in (VoiceState.SPEAKING, VoiceState.THINKING, VoiceState.TRANSCRIBING):
                return

        if self._manager.state != VoiceState.SPEAKING and not self._player.is_playing:
            self._manager.on_turn_completed()
            self.state_changed.emit(self._manager.state)
            if self.is_live_session_active() and not self._restart_scheduled:
                self._maybe_restart_listening()

    def _on_playback_finished(self) -> None:
        logging.debug(f"[VoiceController] _on_playback_finished: manager_state={self._manager.state} live={self.is_live_session_active()}")
        self._mic_manager.barge_in_monitoring = False

        if self._manager.state == VoiceState.INTERRUPTED or self.is_live_session_active():
            if self.is_live_session_active() and not self._is_shutting_down:
                logging.debug("[VoiceController] _on_playback_finished: Live mode active — restarting listening for next turn")
                self._restart_scheduled = False
                self.reset()
                self._maybe_restart_listening()
            return

        if self._manager.state not in (VoiceState.SPEAKING, VoiceState.THINKING):
            logging.debug("[VoiceController] _on_playback_finished ignored: state is not valid for completion")
            return

        self._manager.on_turn_completed()
        self.state_changed.emit(self._manager.state)
        
        if not self._restart_scheduled:
            self._maybe_restart_listening()

    def _on_silence_detected(self) -> None:
        if self._manager.state == VoiceState.LISTENING:
            history = None
            if self._history_provider is not None:
                try:
                    history = self._history_provider()
                except Exception as hist_err:
                    logging.warning(f"[VoiceController] Failed to resolve history from provider: {hist_err}")
            logging.debug(f"[VoiceController] _on_silence_detected: stopping with history={'yes' if history else 'none'}")
            self.stop_listening(history=history)
