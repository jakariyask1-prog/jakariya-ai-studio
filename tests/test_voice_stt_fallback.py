"""Unit test for automatic STT fallback to Google STT when primary STT fails (quota/network)."""

import unittest
from unittest.mock import MagicMock
from app.voice.business_logic.pipeline.conversation_pipeline import PipelineWorker
from app.voice.voice_service import VoiceService
from app.voice.business_logic.stt.stt_registry import STTRegistry
from app.voice.business_logic.tts.tts_registry import TTSRegistry
from app.voice.business_logic.stt.stt_provider import STTProvider


class FailingSTT(STTProvider):
    provider_id = "failing_stt"
    display_name = "Failing STT"

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        raise RuntimeError("ElevenLabs STT quota exceeded (0 credits remaining).")


class MockGoogleSTT(STTProvider):
    provider_id = "google_stt"
    display_name = "Google STT (Free)"

    def is_available(self) -> bool:
        return True

    def transcribe(self, audio_bytes: bytes, language: str) -> str:
        return "Hello world fallback transcript"


class TestSTTFallback(unittest.TestCase):
    def test_stt_fallback_to_google(self):
        stt_reg = STTRegistry([FailingSTT(), MockGoogleSTT()])
        tts_reg = TTSRegistry([])
        service = VoiceService(stt_reg, tts_reg)
        service.settings.stt_provider_id = "failing_stt"

        worker = PipelineWorker(service)
        primary = service.active_stt_provider()

        # Primary transcribe throws exception, worker should fall back to google_stt
        transcript = worker._transcribe_with_fallback(primary, b"fake_audio", "en")
        self.assertEqual(transcript, "Hello world fallback transcript")


if __name__ == "__main__":
    unittest.main()
