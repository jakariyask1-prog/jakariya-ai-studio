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


class MockSTT(object):
    provider_id = "mock_stt"
    display_name = "Mock STT"

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        return "নমস্কার আমি জাকারিয়া স্টুডিও"


class MockTTS(object):
    provider_id = "mock_tts"
    display_name = "Mock TTS"

    def is_available(self) -> bool:
        return True

    def synthesise(self, text: str, language: str) -> bytes:
        return b"mock_pcm_audio_bytes_data"


class MockMic(MicrophoneManager):
    _FAKE_WAV = b"RIFF" + b"\x00" * 40 + (b"\x00" * 7000)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_recording = False

    def start_recording(self, sample_rate=16000):
        self._is_recording = True
        self.recording_started.emit()
        return True

    def stop_recording(self):
        self._is_recording = False
        self.recording_stopped.emit()
        return self._FAKE_WAV

    def get_wav_and_clear(self):
        return self._FAKE_WAV


class MockPlayer(AudioPlayer):
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
        self._is_playing = False
        self.playback_finished.emit()
        self.state_changed.emit(False)


class SeparateVoiceAndLiveModeTests(unittest.TestCase):
    """Explicit tests verifying Microphone Single-Turn Mode vs Live Mode."""

    def setUp(self):
        self.stt_registry = STTRegistry([MockSTT()])
        self.tts_registry = TTSRegistry([MockTTS()])
        self.settings = VoiceSettings(
            stt_provider_id="mock_stt",
            tts_provider_id="mock_tts",
            auto_send=False,
            voice_response=True,
            language="bn",
        )
        self.service = VoiceService(self.stt_registry, self.tts_registry, self.settings)
        self.manager = VoiceManager(self.service)
        self.mic = MockMic()
        self.player = MockPlayer()

        self.controller = VoiceController(
            self.manager,
            microphone_manager=self.mic,
            audio_player=self.player,
        )
        self.controller.audio_ready.connect(self.player.append_bytes)

    def tearDown(self):
        self.controller.shutdown()

    @patch("app.voice.business_logic.pipeline.conversation_pipeline.ClaudeClient")
    def test_single_turn_microphone_mode(self, mock_claude):
        """Test Single-Turn Microphone Mode: records, transcribes to input box, returns READY without looping."""
        self.assertFalse(self.controller.is_live_session_active())

        # Start listening (Single STT Mode)
        self.controller.start_listening()
        self.assertEqual(self.controller.state, VoiceState.LISTENING)
        self.assertTrue(self.mic.is_recording)

        loop = QEventLoop()
        transcript_received = []

        def on_transcript(t):
            transcript_received.append(t)

        self.controller.transcript_ready.connect(on_transcript)
        self.controller._pipeline.turn_completed.connect(loop.quit)

        # Stop listening (Pure STT Mode)
        self.controller.stop_listening(history=None)

        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        # Verify transcript was generated
        self.assertEqual(transcript_received, ["নমস্কার আমি জাকারিয়া স্টুডিও"])

        # Verify state returned to READY cleanly without starting a new listening turn
        self.assertEqual(self.controller.state, VoiceState.READY)
        self.assertFalse(self.mic.is_recording)
        self.assertFalse(self.controller.is_live_session_active())
        mock_claude.assert_not_called()

    @patch("app.voice.business_logic.pipeline.conversation_pipeline.ClaudeClient")
    def test_continuous_live_mode_lifecycle(self, mock_claude):
        """Test Live Mode: continuous loop (Listening -> Transcribing -> Thinking -> Speaking -> Listening)."""
        instance = MagicMock()
        instance.ask_stream.return_value = ["আমি আপনার এআই সহকারী।", " বলুন কিভাবে সাহায্য করতে পারি?"]
        mock_claude.return_value = instance

        # Start Live Mode
        self.controller.start_live_session()
        self.assertTrue(self.controller.is_live_session_active())
        self.assertEqual(self.controller.state, VoiceState.LISTENING)

        # Complete Turn 1
        loop = QEventLoop()
        self.controller._pipeline.turn_completed.connect(loop.quit)
        self.controller.stop_listening()

        QTimer.singleShot(2000, loop.quit)
        loop.exec()

        # Simulate Audio Player finished playing TTS output
        loop_playback = QEventLoop()

        def on_state(st):
            if st == VoiceState.LISTENING:
                loop_playback.quit()

        self.controller.state_changed.connect(on_state)
        self.player.stop()

        QTimer.singleShot(1000, loop_playback.quit)
        loop_playback.exec()

        # Verify system automatically returned to LISTENING for Turn 2
        self.assertTrue(self.controller.is_live_session_active())
        self.assertEqual(self.controller.state, VoiceState.LISTENING)
        self.assertTrue(self.mic.is_recording)

        # Now stop Live Mode
        self.controller.stop_live_session()
        self.assertFalse(self.controller.is_live_session_active())
        self.assertIn(self.controller.state, (VoiceState.READY, VoiceState.INTERRUPTED))


if __name__ == "__main__":
    unittest.main()
