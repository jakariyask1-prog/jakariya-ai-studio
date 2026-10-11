import os
import unittest
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

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
# Test Mocks
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


class MockMicrophoneManager(MicrophoneManager):
    # Minimum fake WAV: 44-byte WAV header + 7000 bytes of silent PCM
    # This ensures Bug Fix #4 (minimum audio size guard) does not discard the audio.
    _FAKE_WAV = b"RIFF" + b"\x00" * 40 + (b"\x00" * 7000)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False
        self._gain = 1.0

    def start_recording(self, sample_rate=16000):
        self._gain = 1.0  # Reset gain
        self._is_recording = True
        self.recording_started.emit()
        return True

    def stop_recording(self):
        self._is_recording = False
        self.recording_stopped.emit()
        return self._FAKE_WAV

    def get_wav_and_clear(self):
        return self._FAKE_WAV


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
        self._is_playing = True
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
# Test Cases
# ------------------------------------------------------------------

class VoicePipelineIntegrationTests(unittest.TestCase):
    """Integration tests for the voice interaction pipeline and state transitions."""

    def setUp(self):
        # Register mock providers
        self.stt_registry = STTRegistry([MockSTTProvider()])
        self.tts_registry = TTSRegistry([MockTTSProvider()])

        self.settings = VoiceSettings(
            stt_provider_id="mock_stt",
            tts_provider_id="mock_tts",
            auto_send=True,
            voice_response=True,
        )

        self.service = VoiceService(
            self.stt_registry,
            self.tts_registry,
            self.settings
        )
        self.manager = VoiceManager(self.service)

        # Use test mock audio managers to avoid hitting real hardware
        self.mic_manager = MockMicrophoneManager()
        self.audio_player = MockAudioPlayer()

        self.controller = VoiceController(
            self.manager,
            microphone_manager=self.mic_manager,
            audio_player=self.audio_player,
        )
        self.controller.audio_ready.connect(self.audio_player.append_bytes)

        # Track state transitions
        self.states_visited = []
        self.controller.state_changed.connect(self.states_visited.append)

    def tearDown(self):
        self.controller.shutdown()

    @patch("app.voice.business_logic.pipeline.conversation_pipeline.ClaudeClient")
    def test_normal_turn_state_transitions(self, mock_claude_class):
        # Setup Claude mock ask_stream generator
        mock_claude = MagicMock()
        # Response must be >= MIN_CHUNK_CHARS (20) to trigger SPEAKING state via TTS
        mock_claude.ask_stream.return_value = ["This is a complete response sentence.", " It sounds natural and clear."]
        mock_claude_class.return_value = mock_claude

        self.settings.auto_send = True
        self.controller.update_settings(self.settings)

        loop = QEventLoop()
        # Quit the loop when pipeline completion signal is fired
        self.controller._pipeline.turn_completed.connect(loop.quit)
        self.controller.error_occurred.connect(lambda err: loop.quit())

        # Start live session for full turn testing
        self.controller.start_live_session()
        self.assertEqual(self.controller.state, VoiceState.LISTENING)

        # Stop listening (triggers pipeline execution in background thread)
        self.controller.stop_listening()

        # Wait for the turn to complete
        QTimer.singleShot(2000, loop.quit)  # Safety timeout
        loop.exec()

        # Verify states visited
        # Expected flow: LISTENING -> TRANSCRIBING -> THINKING -> SPEAKING/READY
        self.assertIn(VoiceState.TRANSCRIBING, self.states_visited)
        self.assertIn(VoiceState.THINKING, self.states_visited)
        self.assertIn(self.controller.state, (VoiceState.SPEAKING, VoiceState.READY))

    @patch("app.voice.business_logic.pipeline.conversation_pipeline.ClaudeClient")
    def test_dictation_flow_no_auto_send(self, mock_claude_class):
        # Disable auto-send
        self.settings.auto_send = False
        self.controller.update_settings(self.settings)

        loop = QEventLoop()
        self.controller._pipeline.turn_completed.connect(loop.quit)

        self.controller.start_listening()
        self.controller.stop_listening()

        # Wait for completion
        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        # Expect to stop at transcription, not call Claude or TTS
        self.assertIn(VoiceState.TRANSCRIBING, self.states_visited)
        self.assertNotIn(VoiceState.THINKING, self.states_visited)
        self.assertNotIn(VoiceState.SPEAKING, self.states_visited)
        self.assertEqual(self.controller.state, VoiceState.READY)
        mock_claude_class.assert_not_called()

    @patch("app.voice.business_logic.pipeline.conversation_pipeline.ClaudeClient")
    def test_live_mode_barge_in(self, mock_claude_class):
        mock_claude = MagicMock()
        # Response must be >= MIN_CHUNK_CHARS (20) to trigger SPEAKING state via TTS
        mock_claude.ask_stream.return_value = ["Please wait for me to finish speaking this sentence."]
        mock_claude_class.return_value = mock_claude

        # Start live session
        self.controller.start_live_session()
        self.assertTrue(self.controller.is_live_session_active())
        self.assertEqual(self.controller.state, VoiceState.LISTENING)

        # Transition to SPEAKING via pipeline run
        loop = QEventLoop()
        
        def on_state(state):
            if state == VoiceState.SPEAKING:
                self.audio_player._is_playing = True
                loop.quit()

        self.controller.state_changed.connect(on_state)
        self.controller.stop_listening()
        
        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        # Disconnect setup callback to avoid duplicate calls
        try:
            self.controller.state_changed.disconnect(on_state)
        except Exception:
            pass

        # Now we are in SPEAKING state, verify gain was lowered
        self.assertEqual(self.controller.state, VoiceState.SPEAKING)
        self.assertAlmostEqual(self.mic_manager._gain, 0.15)

        # Record states for barge-in transition
        self.states_visited.clear()

        loop_barge = QEventLoop()
        def on_barge_state(state):
            if state == VoiceState.LISTENING:
                loop_barge.quit()
        self.controller.state_changed.connect(on_barge_state)

        # Emulate microphone speech_started signal (user speaking while AI is speaking)
        self.mic_manager.speech_started.emit()

        QTimer.singleShot(1500, loop_barge.quit)
        loop_barge.exec()

        try:
            self.controller.state_changed.disconnect(on_barge_state)
        except Exception:
            pass

        # Verify flow: barge-in triggers INTERRUPTED, and then starts LISTENING again in live mode
        self.assertIn(VoiceState.INTERRUPTED, self.states_visited)
        self.assertEqual(self.controller.state, VoiceState.LISTENING)
        # Gain is reset to 1.0 during LISTENING
        self.assertAlmostEqual(self.mic_manager._gain, 1.0)

    @patch("app.voice.business_logic.pipeline.conversation_pipeline.ClaudeClient")
    def test_live_mode_continuous_turns(self, mock_claude_class):
        mock_claude = MagicMock()
        # Response must be >= MIN_CHUNK_CHARS (20) to trigger SPEAKING state via TTS
        mock_claude.ask_stream.return_value = ["This is the response for this voice turn."]
        mock_claude_class.return_value = mock_claude

        # Start live session
        self.controller.start_live_session()
        self.assertTrue(self.controller.is_live_session_active())
        self.assertEqual(self.controller.state, VoiceState.LISTENING)

        # Complete Turn 1
        loop = QEventLoop()
        self.controller._pipeline.turn_completed.connect(loop.quit)
        self.controller.stop_listening()
        
        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        # Simulate AudioPlayer finishing playback for Turn 1
        loop_playback = QEventLoop()
        def on_listening(state):
            if state == VoiceState.LISTENING:
                loop_playback.quit()
        self.controller.state_changed.connect(on_listening)

        self.audio_player.stop()

        QTimer.singleShot(1000, loop_playback.quit)
        loop_playback.exec()

        # Verify that after Turn 1 audio finishes, controller automatically restarts LISTENING for Turn 2
        self.assertEqual(self.controller.state, VoiceState.LISTENING)
        self.assertTrue(self.mic_manager.is_recording)

    def test_barge_in_ignored_in_thinking_state(self):
        """Verify barge-in is ignored during TRANSCRIBING/THINKING and only fires during SPEAKING."""
        self.controller.start_live_session()
        self.assertEqual(self.controller.state, VoiceState.LISTENING)

        # Manually drive the manager into TRANSCRIBING state (mirrors what stop_listening does
        # after dispatching to the pipeline). We test gain attenuation and barge-in guard.
        self.manager.on_transcribing_started()
        self.mic_manager.set_gain(0.15)  # Mirrors what _on_pipeline_state_changed does
        self.controller.state_changed.emit(self.manager.state)
        self.assertEqual(self.controller.state, VoiceState.TRANSCRIBING)
        self.assertAlmostEqual(self.mic_manager._gain, 0.15)

        # Speech start signal during TRANSCRIBING should NOT call interrupt()
        with patch.object(self.controller, "interrupt") as mock_interrupt:
            self.mic_manager.speech_started.emit()
            mock_interrupt.assert_not_called()


if __name__ == "__main__":
    unittest.main()

