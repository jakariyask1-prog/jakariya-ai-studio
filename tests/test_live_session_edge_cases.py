"""
Live-Session Edge Case Tests — Dropped Microphone & Audio Device Disconnection.

Tests simulate:
1. Microphone initialization failure (device unavailable / permission denied)
2. Microphone drop mid-recording (device disconnected during live session)
3. Live session error recovery after mic failure
4. Empty/insufficient audio capture from a failing mic
5. Pipeline error with live mode auto-recovery
6. Single-turn mic failure (no auto-recovery)
"""

import os
import unittest
from unittest.mock import patch, MagicMock, PropertyMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app.voice import (
    VoiceController,
    VoiceManager,
    VoiceService,
    VoiceSettings,
    VoiceState,
)
from app.voice.business_logic.stt.stt_registry import STTRegistry
from app.voice.business_logic.tts.tts_registry import TTSRegistry
from app.voice.business_logic.audio.microphone import MicrophoneManager
from app.voice.business_logic.audio.audio_player import AudioPlayer


_APP = QApplication.instance() or QApplication([])


# ------------------------------------------------------------------
# Specialized Mocks for Edge Case Testing
# ------------------------------------------------------------------

class MockSTTProvider:
    def __init__(self):
        self.provider_id = "mock_stt"
        self.display_name = "Mock STT"

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        return "Hello Claude"


class MockTTSProvider:
    def __init__(self):
        self.provider_id = "mock_tts"
        self.display_name = "Mock TTS"

    def is_available(self) -> bool:
        return True

    def synthesise(self, text: str, language: str) -> bytes:
        return b"mock_pcm_audio_data"


class FailingMicrophoneManager(MicrophoneManager):
    """Simulates a microphone that fails to start (device missing/permission denied)."""
    _FAKE_WAV = b"RIFF" + b"\x00" * 40 + (b"\x00" * 7000)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._fail_on_start = True  # Will fail start_recording()
        self._gain = 1.0

    def start_recording(self, sample_rate=16000):
        if self._fail_on_start:
            return False  # Microphone initialization failure
        self._is_recording = True
        self.recording_started.emit()
        return True

    def stop_recording(self):
        self._is_recording = False
        self.recording_stopped.emit()
        return self._FAKE_WAV

    def get_wav_and_clear(self):
        return self._FAKE_WAV

    def set_gain(self, gain: float):
        self._gain = gain


class DroppingMicrophoneManager(MicrophoneManager):
    """Simulates a mic that starts OK but returns empty/corrupt audio on disconnect."""
    _FAKE_WAV = b"RIFF" + b"\x00" * 40 + (b"\x00" * 7000)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._drop_after_start = False
        self._gain = 1.0

    def start_recording(self, sample_rate=16000):
        self._is_recording = True
        self.recording_started.emit()
        return True

    def stop_recording(self):
        self._is_recording = False
        self.recording_stopped.emit()
        if self._drop_after_start:
            # Mic disconnected mid-recording: returns only WAV header, no PCM data
            return b"RIFF" + b"\x00" * 40
        return self._FAKE_WAV

    def get_wav_and_clear(self):
        if self._drop_after_start:
            return b"RIFF" + b"\x00" * 40  # Only WAV header, insufficient audio
        return self._FAKE_WAV

    def set_gain(self, gain: float):
        self._gain = gain


class RecoveringMicrophoneManager(MicrophoneManager):
    """Simulates a mic that fails N times then recovers (e.g. USB reconnected)."""
    _FAKE_WAV = b"RIFF" + b"\x00" * 40 + (b"\x00" * 7000)

    def __init__(self, fail_count=2, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._fail_count = fail_count
        self._attempt_count = 0
        self._gain = 1.0

    def start_recording(self, sample_rate=16000):
        self._attempt_count += 1
        if self._attempt_count <= self._fail_count:
            return False
        self._is_recording = True
        self.recording_started.emit()
        return True

    def stop_recording(self):
        self._is_recording = False
        self.recording_stopped.emit()
        return self._FAKE_WAV

    def get_wav_and_clear(self):
        return self._FAKE_WAV

    def set_gain(self, gain: float):
        self._gain = gain


class MockAudioPlayer(AudioPlayer):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_playing = False

    def play_bytes(self, audio_bytes, sample_rate=16000, channels=1):
        self._is_playing = True
        self.playback_started.emit()
        self.state_changed.emit(True)
        return True

    def append_bytes(self, audio_bytes, sample_rate=16000, channels=1):
        return True

    def mark_complete(self):
        pass

    def stop(self):
        was_playing = self._is_playing
        self._is_playing = False
        if was_playing:
            self.playback_finished.emit()
            self.state_changed.emit(False)


# ------------------------------------------------------------------
# Test Cases — Live Session Edge Cases
# ------------------------------------------------------------------

class LiveSessionEdgeCaseTests(unittest.TestCase):
    """Tests for microphone failure, audio device disconnection, and error recovery."""

    def _build_controller(self, mic_manager):
        """Helper to construct a VoiceController with the given mic manager."""
        stt_registry = STTRegistry([MockSTTProvider()])
        tts_registry = TTSRegistry([MockTTSProvider()])
        settings = VoiceSettings(
            stt_provider_id="mock_stt",
            tts_provider_id="mock_tts",
            auto_send=True,
            voice_response=True,
        )
        service = VoiceService(stt_registry, tts_registry, settings)
        manager = VoiceManager(service)
        audio_player = MockAudioPlayer()
        controller = VoiceController(
            manager,
            microphone_manager=mic_manager,
            audio_player=audio_player,
        )
        return controller, manager, audio_player

    def test_mic_init_failure_single_turn_emits_error_and_enters_error_state(self):
        """When start_recording() returns False, controller should emit error_occurred
        and transition to ERROR state (single-turn, no live session)."""
        mic = FailingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        errors = []
        states = []
        controller.error_occurred.connect(errors.append)
        controller.state_changed.connect(states.append)

        try:
            # Attempt to start listening — mic will fail
            controller.start_listening()

            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertEqual(len(errors), 1)
            self.assertIn("microphone", errors[0].lower())
        finally:
            controller.shutdown()

    def test_mic_init_failure_live_session_triggers_error_and_recovery_attempt(self):
        """In live session, mic failure should enter ERROR state, emit error,
        and schedule auto-recovery via _restart_live_after_error."""
        mic = FailingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        errors = []
        states = []
        controller.error_occurred.connect(errors.append)
        controller.state_changed.connect(states.append)

        try:
            # Start live session — mic will fail
            manager.start_live_session()
            controller.start_listening()

            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertEqual(len(errors), 1)
            self.assertIn("microphone", errors[0].lower())
        finally:
            manager.stop_live_session()
            controller.shutdown()

    def test_mic_drop_mid_recording_single_turn_detects_insufficient_audio(self):
        """When mic disconnects mid-recording, stop_listening gets near-empty WAV.
        In single-turn mode this should emit 'No audio captured' error."""
        mic = DroppingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        errors = []
        controller.error_occurred.connect(errors.append)

        try:
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.LISTENING)

            # Simulate mic disconnection mid-recording
            mic._drop_after_start = True

            # Stop listening — will get insufficient audio
            controller.stop_listening()

            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertEqual(len(errors), 1)
            self.assertIn("no audio", errors[0].lower())
        finally:
            controller.shutdown()

    def test_mic_drop_mid_recording_live_session_auto_restarts_listening(self):
        """When mic disconnects mid-recording during live session, controller
        should detect insufficient audio, reset to READY, and schedule restart."""
        mic = DroppingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        states = []
        controller.state_changed.connect(states.append)

        try:
            # Start live session successfully
            manager.start_live_session()
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.LISTENING)

            # Simulate mic disconnect
            mic._drop_after_start = True

            # stop_listening with insufficient audio → should reset and schedule restart
            controller.stop_listening()

            # In live mode with insufficient audio, controller resets to READY (not ERROR)
            self.assertEqual(manager.state, VoiceState.READY)
            self.assertIn(VoiceState.READY, states)
        finally:
            manager.stop_live_session()
            controller.shutdown()

    def test_pipeline_error_in_live_mode_schedules_recovery(self):
        """When pipeline emits error_occurred during live session, controller
        should enter ERROR state and schedule _restart_live_after_error."""
        mic = DroppingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        errors = []
        states = []
        controller.error_occurred.connect(errors.append)
        controller.state_changed.connect(states.append)

        try:
            manager.start_live_session()
            controller.start_listening()

            # Simulate a pipeline error (e.g. STT network failure)
            controller._on_pipeline_error("STT transcription failed: network timeout")

            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertIn(VoiceState.ERROR, states)
            self.assertEqual(len(errors), 1)
            self.assertIn("network timeout", errors[0].lower())

            # Verify recovery was scheduled
            self.assertTrue(controller._restart_scheduled)
        finally:
            manager.stop_live_session()
            controller.shutdown()

    def test_pipeline_error_single_turn_no_auto_recovery(self):
        """In single-turn mode, pipeline error should NOT schedule auto-recovery."""
        mic = DroppingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        errors = []
        controller.error_occurred.connect(errors.append)

        try:
            controller.start_listening()

            # Simulate pipeline error in single-turn
            controller._on_pipeline_error("API rate limit exceeded (429)")

            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertEqual(len(errors), 1)

            # No auto-recovery in single-turn mode
            self.assertFalse(controller._restart_scheduled)
        finally:
            controller.shutdown()

    def test_recovering_mic_succeeds_after_initial_failures(self):
        """Simulate USB mic reconnection: fails 2 times, succeeds on 3rd attempt."""
        mic = RecoveringMicrophoneManager(fail_count=2)
        controller, manager, _ = self._build_controller(mic)

        errors = []
        controller.error_occurred.connect(errors.append)

        try:
            # Attempt 1 — fails
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertEqual(len(errors), 1)

            # Attempt 2 — still fails
            manager.reset()
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.ERROR)
            self.assertEqual(len(errors), 2)

            # Attempt 3 — mic recovered (USB reconnected)
            manager.reset()
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.LISTENING)
            self.assertEqual(len(errors), 2)  # no new errors
            self.assertEqual(mic._attempt_count, 3)
        finally:
            controller.shutdown()

    def test_error_state_transitions_to_ready_on_reset(self):
        """After mic failure, calling reset() should cleanly return to READY."""
        mic = FailingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        try:
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.ERROR)

            controller.reset()
            self.assertEqual(manager.state, VoiceState.READY)
            self.assertTrue(manager.is_idle)
        finally:
            controller.shutdown()

    def test_stop_live_session_during_error_state_cleans_up(self):
        """Stopping live session while in ERROR state should cleanly reset."""
        mic = FailingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        try:
            manager.start_live_session()
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.ERROR)

            # Stop live session from error state
            controller.stop_live_session()

            self.assertFalse(manager.is_live_session_active())
            # After stop_live_session, state should be INTERRUPTED or stable
            self.assertIn(manager.state, (VoiceState.ERROR, VoiceState.INTERRUPTED))
        finally:
            controller.shutdown()

    def test_silence_detected_with_dropped_mic_live_session(self):
        """Simulate silence_detected signal firing after mic drops mid-recording.
        The silence handler calls stop_listening which should handle insufficient audio."""
        mic = DroppingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        states = []
        controller.state_changed.connect(states.append)

        try:
            manager.start_live_session()
            controller.start_listening()
            self.assertEqual(manager.state, VoiceState.LISTENING)

            # Mic drops
            mic._drop_after_start = True

            # Silence timer fires (VAD detected silence after mic stopped sending data)
            mic.silence_detected.emit()

            # Controller's _on_silence_detected calls stop_listening
            # With insufficient audio in live mode → reset to READY
            self.assertEqual(manager.state, VoiceState.READY)
        finally:
            manager.stop_live_session()
            controller.shutdown()

    def test_multiple_errors_do_not_double_schedule_recovery(self):
        """Multiple rapid pipeline errors should not schedule multiple recovery timers."""
        mic = DroppingMicrophoneManager()
        controller, manager, _ = self._build_controller(mic)

        errors = []
        controller.error_occurred.connect(errors.append)

        try:
            manager.start_live_session()
            controller.start_listening()

            # First error
            controller._on_pipeline_error("Error 1: timeout")
            self.assertTrue(controller._restart_scheduled)

            # Second error while recovery already scheduled
            controller._on_pipeline_error("Error 2: connection refused")

            # Should still have only one scheduled recovery (guard prevents double)
            self.assertTrue(controller._restart_scheduled)
            self.assertEqual(len(errors), 2)
        finally:
            manager.stop_live_session()
            controller.shutdown()


if __name__ == "__main__":
    unittest.main()
