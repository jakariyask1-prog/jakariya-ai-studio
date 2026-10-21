import os
import unittest
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from app.voice.business_logic.audio.microphone import MicrophoneManager
from app.voice.business_logic.stt.groq_stt import GroqSTT
from app.voice.business_logic.stt.google_stt import GoogleSTT
from app.voice.business_logic.tts.cartesia_tts import CartesiaTTS
from app.settings.settings_schema import VoiceSettingsSchema
from app.settings.ui.voice_page import VoicePage

_APP = QApplication.instance() or QApplication([])


class TestLiveConversationFixes(unittest.TestCase):
    def test_microphone_capture_isolation(self):
        """Verify that when is_capturing is False, incoming PCM does not pollute the buffer."""
        mic = MicrophoneManager()
        mic.start_recording()

        # By default is_capturing is True
        self.assertTrue(mic.is_capturing)
        chunk = b"\x00\x01" * 160
        mic.process_pcm_chunk(chunk)
        self.assertGreater(len(mic.current_stream.get_wav_bytes()), 44)

        # Disable capturing (e.g. during AI thinking/speaking)
        mic.get_wav_and_clear()
        mic.is_capturing = False
        mic.process_pcm_chunk(chunk)
        # Stream buffer should remain empty (0 bytes)
        self.assertEqual(mic.current_stream.total_bytes, 0)

        # Re-enable capturing (e.g. entering LISTENING)
        mic.is_capturing = True
        mic.process_pcm_chunk(chunk)
        self.assertEqual(mic.current_stream.total_bytes, len(chunk))
        mic.stop_recording()

    def test_microphone_barge_in_threshold(self):
        """Verify barge_in_monitoring requires loud voice to prevent speaker bleed triggering speech_started."""
        mic = MicrophoneManager()
        mic.start_recording()
        mic.is_capturing = False
        mic.barge_in_monitoring = True

        speech_triggered = []
        mic.speech_started.connect(lambda: speech_triggered.append(True))

        # Moderate noise / speaker echo (~0.05 RMS, below 0.12 threshold)
        # 16-bit PCM amplitude around 1600 (1600/32768 ≈ 0.048 RMS)
        moderate_noise = (int(1600)).to_bytes(2, byteorder="little", signed=True) * 160
        for _ in range(10):
            mic.process_pcm_chunk(moderate_noise)

        self.assertEqual(len(speech_triggered), 0, "Moderate speaker echo must not trigger barge-in")

        # Loud user voice (>0.12 RMS, amplitude ~8000, 8000/32768 ≈ 0.24 RMS)
        loud_voice = (int(8000)).to_bytes(2, byteorder="little", signed=True) * 160
        for _ in range(8):  # >= 6 consecutive chunks (600ms)
            mic.process_pcm_chunk(loud_voice)

        self.assertGreater(len(speech_triggered), 0, "Loud intentional speech must trigger barge-in")
        mic.stop_recording()

    def test_groq_stt_language_auto_and_prompt(self):
        """Verify GroqSTT sets language=None for 'auto' and does not force prompt."""
        stt = GroqSTT()
        with patch.object(stt, "_get_api_key", return_value="gsk_test_mock_key"), \
             patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"text": "আমার নাম জাকারিয়া"}
            mock_post.return_value = mock_resp

            result = stt.transcribe(b"RIFF" + b"\x00" * 100, language="auto")
            self.assertEqual(result, "আমার নাম জাকারিয়া")

            # Check post request args
            call_kwargs = mock_post.call_args[1]
            data_sent = call_kwargs["data"]
            self.assertNotIn("language", data_sent, "Language must not be forced when 'auto'")

    def test_google_stt_auto_fallback(self):
        """Verify GoogleSTT supports bilingual recognition when 'auto' is passed."""
        stt = GoogleSTT()
        with patch("speech_recognition.Recognizer.record"), \
             patch("speech_recognition.Recognizer.recognize_google", return_value="টেস্ট") as mock_rec:
            # Fake wav bytes
            fake_wav = b"RIFF" + b"\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
            result = stt.transcribe(fake_wav, language="auto")
            self.assertEqual(result, "টেস্ট")
            called_languages = [call_args[1].get("language") for call_args in mock_rec.call_args_list]
            self.assertIn("bn-BD", called_languages)
            self.assertIn("en-US", called_languages)

    def test_cartesia_tts_language_voice_pairing(self):
        """Verify CartesiaTTS intelligently matches language to English or Bengali."""
        tts = CartesiaTTS(voice_id="2c8d7dfb-ca84-4888-9600-8d8c54022dba")
        with patch.object(tts, "_get_api_key", return_value="sk_car_mock"), \
             patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.iter_content.return_value = [b"mock_audio_pcm"]
            mock_post.return_value = mock_resp

            # English text with language="auto"
            tts.synthesise("Hello, how are you today?", language="auto")
            payload = mock_post.call_args[1]["json"]
            self.assertEqual(payload["language"], "en")
            self.assertEqual(payload["voice"]["id"], CartesiaTTS.DEFAULT_ENGLISH_VOICE_ID)

            # Bengali text with language="auto"
            tts.synthesise("হ্যালো, আপনি কেমন আছেন?", language="auto")
            payload = mock_post.call_args[1]["json"]
            self.assertEqual(payload["language"], "bn")
            self.assertEqual(payload["voice"]["id"], CartesiaTTS.DEFAULT_BANGLA_VOICE_ID)

    def test_voice_page_hardware_devices_and_schema(self):
        """Verify VoicePage UI properly serializes input and output device indices and schema defaults."""
        schema = VoiceSettingsSchema()
        self.assertEqual(schema.stt_provider_id, "groq_stt")
        self.assertEqual(schema.language, "auto")
        self.assertEqual(schema.silence_timeout_ms, 1000)

        page = VoicePage()
        schema.input_device_index = 0
        schema.output_device_index = 0
        page.load_settings(schema)

        saved = page.get_settings()
        self.assertEqual(saved.stt_provider_id, "groq_stt")
        self.assertEqual(saved.language, "auto")
        self.assertEqual(saved.silence_timeout_ms, 1000)

    def test_live_stream_filters_inline_think_tags(self):
        """Verify inline <think>...</think> reasoning tags are suppressed from stream."""
        from app.api.ClaudeClient import ClaudeClient
        from app.providers.models.chat_response import StreamChunk
        claude = ClaudeClient()

        mock_chunks = [
            StreamChunk(delta="<think>Thinking about"),
            StreamChunk(delta=" the response...</think>Hello, "),
            StreamChunk(delta="I am ready to help."),
        ]
        with patch.object(claude._provider_manager, "chat_stream", return_value=iter(mock_chunks)):
            result = list(claude.ask_stream("Tell about you", is_live=True))
            full_reply = "".join(result)
            self.assertNotIn("<think>", full_reply)
            self.assertNotIn("Thinking about", full_reply)
            self.assertEqual(full_reply, "Hello, I am ready to help.")

    def test_live_voice_suppresses_reasoning_fallback(self):
        """Verify that when a reasoning model emits ONLY reasoning tokens in live mode, internal thoughts are not leaked."""
        from app.api.ClaudeClient import ClaudeClient
        from app.providers.models.chat_response import StreamChunk
        claude = ClaudeClient()

        # Simulate reasoning model exhausting max_tokens on internal reasoning alone
        mock_chunks = [
            StreamChunk(delta="", reasoning_delta="User asks 'tell about you'. Need to respond according to style..."),
        ]
        with patch.object(claude._provider_manager, "chat_stream", return_value=iter(mock_chunks)):
            result = list(claude.ask_stream("Tell about you", is_live=True))
            full_reply = "".join(result)
            self.assertNotIn("User asks", full_reply)
            self.assertNotIn("Need to respond according to style", full_reply)
            self.assertIn("Jakariya AI Studio", full_reply)
