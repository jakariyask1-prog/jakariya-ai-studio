"""Unit tests for Phase 7 Step 3 Audio Engine layer."""

import os
import struct
import unittest
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from app.voice.business_logic.audio import (
    AudioChunk,
    AudioFormat,
    AudioLevelMeter,
    AudioPlayer,
    AudioStream,
    MicrophoneManager,
    SpeakerManager,
)

_APP = QApplication.instance() or QApplication([])


class AudioEngineTests(unittest.TestCase):
    """Test suite for Audio Engine layer."""

    def test_audio_level_meter_rms_calculation(self):
        meter = AudioLevelMeter()
        samples = [0, 16384, -16384, 0] * 100
        pcm_data = struct.pack(f"<{len(samples)}h", *samples)
        rms = meter.calculate_rms(pcm_data)
        self.assertAlmostEqual(rms, 0.35355, delta=0.01)
        smoothed = meter.update(pcm_data)
        self.assertGreater(smoothed, 0.0)

    def test_audio_stream_wav_generation(self):
        stream = AudioStream(AudioFormat(sample_rate=16000, channels=1, bits_per_sample=16))
        samples = [1000] * 320
        pcm_data = struct.pack(f"<{len(samples)}h", *samples)
        stream.append(pcm_data)
        self.assertEqual(stream.total_bytes, len(pcm_data))

        wav = stream.get_wav_bytes()
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertIn(b"WAVE", wav)
        self.assertIn(b"fmt ", wav)
        self.assertIn(b"data", wav)

    def test_microphone_manager_recording_lifecycle(self):
        mic = MicrophoneManager()
        devices = mic.list_devices()
        self.assertGreater(len(devices), 0)

        started = mic.start_recording(16000)
        if started:
            self.assertTrue(mic.is_recording)

            samples = [2000] * 160
            pcm_data = struct.pack(f"<{len(samples)}h", *samples)
            mic.process_pcm_chunk(pcm_data)
            self.assertGreater(mic.current_level, 0.0)

            wav_bytes = mic.stop_recording()
            self.assertFalse(mic.is_recording)
            self.assertTrue(wav_bytes.startswith(b"RIFF"))
        else:
            self.assertFalse(mic.is_recording)

    def test_speaker_manager_device_and_volume(self):
        speaker = SpeakerManager()
        devices = speaker.list_devices()
        self.assertGreater(len(devices), 0)

        speaker.set_volume(0.8)
        self.assertEqual(speaker.volume, 0.8)

        speaker.set_muted(True)
        self.assertTrue(speaker.is_muted)
        self.assertEqual(speaker.volume, 0.0)

        speaker.set_muted(False)
        self.assertEqual(speaker.volume, 0.8)

    def test_audio_player_volume_and_state(self):
        player = AudioPlayer()
        player.set_volume(0.65)
        self.assertEqual(player.volume, 0.65)
        self.assertFalse(player.is_playing)


if __name__ == "__main__":
    unittest.main()
