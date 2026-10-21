"""Unit and integration tests for Bilingual (Bangla & English) STT/TTS phonetic intelligence and latency optimizations."""

import unittest
from app.voice.utils.speech_normalizer import normalize_stt_transcript, normalize_tts_text
from app.voice.utils.audio_utils import strip_markdown


class TestBilingualSpeechIntelligence(unittest.TestCase):
    def test_stt_bangla_phonetic_corrections(self):
        """Verify common Whisper & Google STT Bengali phonetic misspellings are corrected."""
        test_cases = [
            ("কেমোন অছেন আপনি?", "কেমন আছেন আপনি?"),
            ("ক্যমন আছোন?", "কেমন আছেন?"),
            ("ক্যামন আচেন?", "কেমন আছেন?"),
            ("আছকের আবোহাও কেমন?", "আজকের আবহাওয়া কেমন?"),
            ("অচকের আবোহাওয়া কি?", "আজকের আবহাওয়া কি?"),
            ("আপনি কি করচেন আর কি বলচেন?", "আপনি কি করছেন আর কি বলছেন?"),
            ("আমি শুনচি আর বুজতে পারচি", "আমি শুনছি আর বুঝতে পারছি"),
            ("ধন্নবাদ আপনার সাহাজ্যের জন্য", "ধন্যবাদ আপনার সাহায্যের জন্য"),
            ("বাঙলাদেশ আমার অহংকার", "বাংলাদেশ আমার অহংকার"),
            ("সঠিক উচ্চারন এবং বানন শিখুন", "সঠিক উচ্চারণ এবং বানান শিখুন"),
            ("খুব সুন্দোর কাজ করসেন", "খুব সুন্দর কাজ করছেন"),
        ]
        for distorted, expected in test_cases:
            # normalize punctuation for comparing semantic transcript text
            cleaned = normalize_stt_transcript(distorted, language="bn")
            cleaned_simple = cleaned.replace("?", "").replace("!", "").strip()
            expected_simple = expected.replace("?", "").replace("!", "").strip()
            self.assertEqual(cleaned_simple, expected_simple, f"Failed for '{distorted}'")

    def test_stt_english_phonetic_corrections(self):
        """Verify common English speech recognition misspellings and accent errors are fixed."""
        test_cases = [
            ("what is the pronounciation of this word", "what is the pronunciation of this word"),
            ("did you mispel that word or mispelling it", "did you misspell that word or misspelling it"),
            ("debelop the python script please", "develop the python script please"),
            ("the bideo and boyce quality is great", "the video and voice quality is great"),
            ("check the wether and temparature tomorrow", "check the weather and temperature tomorrow"),
            ("definately seperate the components", "definitely separate the components"),
            ("it is neccessary to recieve untill monday", "it is necessary to receive until monday"),
            ("the goverment is improving the enviroment", "the government is improving the environment"),
            ("stoodio and pithon coding", "studio and python coding"),
        ]
        for distorted, expected in test_cases:
            cleaned = normalize_stt_transcript(distorted, language="en")
            self.assertEqual(cleaned, expected, f"Failed for '{distorted}'")

    def test_tts_bangla_pronunciation_transliteration(self):
        """Verify English tech and loanwords are phonetically rendered into native Bengali for neural TTS."""
        text = "আজকের আবহাওয়া ভালো। Python এবং Studio দিয়ে AI মডেল তৈরি করুন।"
        res = strip_markdown(text, language="bn")
        # Should convert English loanwords to Bengali script for fluent natural pronunciation
        self.assertIn("পাইথন", res, "Python must be converted to পাইথন for Bengali TTS")
        self.assertIn("স্টুডিও", res, "Studio must be converted to স্টুডিও for Bengali TTS")
        self.assertIn("এআই", res, "AI must be converted to এআই for Bengali TTS")

    def test_tts_english_spelling_articulation(self):
        """Verify letter-by-letter spelled words are formatted with commas for crisp TTS articulation."""
        text = "Accommodation is spelled A-C-C-O-M-M-O-D-A-T-I-O-N."
        res = strip_markdown(text, language="en")
        self.assertIn("A, C, C, O, M, M, O, D, A, T, I, O, N", res)

    def test_tts_currency_and_symbol_expansions(self):
        """Verify symbols and currencies are expanded correctly per language."""
        text_bn = "দাম ৳500 এবং ২০% ছাড়।"
        res_bn = strip_markdown(text_bn, language="bn")
        self.assertIn("টাকা", res_bn)
        self.assertIn("শতাংশ", res_bn)

        text_en = "Price is $50 and 20% discount."
        res_en = strip_markdown(text_en, language="en")
        self.assertIn("dollars", res_en)
        self.assertIn("percent", res_en)

    def test_live_mode_low_latency_silence_timeout(self):
        """Verify live session configures snappy 550ms silence timeout and restores original upon stop."""
        from app.voice import VoiceController, VoiceManager, VoiceService, VoiceSettings
        from app.voice.business_logic.stt.stt_registry import STTRegistry
        from app.voice.business_logic.tts.tts_registry import TTSRegistry
        from tests.test_voice_pipeline import MockSTTProvider, MockTTSProvider, MockMicrophoneManager, MockAudioPlayer

        settings = VoiceSettings(silence_timeout_ms=1200)
        service = VoiceService(STTRegistry([MockSTTProvider()]), TTSRegistry([MockTTSProvider()]), settings)
        manager = VoiceManager(service)
        mic = MockMicrophoneManager()
        player = MockAudioPlayer()
        ctrl = VoiceController(manager, mic, player)

        # Standard mode uses configured 1200ms
        ctrl.update_settings(settings)
        self.assertEqual(mic.silence_timeout_ms, 1200)

        # Starting live session drops silence timeout to 550ms for snappy live turn-taking
        ctrl.start_live_session()
        self.assertEqual(mic.silence_timeout_ms, 550)

        # Stopping live session restores original silence timeout
        ctrl.stop_live_session()
        self.assertEqual(mic.silence_timeout_ms, 1200)
        ctrl.shutdown()


if __name__ == "__main__":
    unittest.main()
