"""Unit tests for Voice Settings, Custom Voices, and TTS Engine integration."""

import os
import unittest
from unittest.mock import patch, MagicMock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from app.settings.settings_schema import VoiceSettingsSchema
from app.settings.ui.voice_page import VoicePage
from app.ui.voice_settings_dialog import VoiceSettingsDialog
from app.voice.voice_settings import VoiceSettings
from app.voice.voice_presets import (
    get_voices_for_provider,
    get_default_voice_for_provider,
    get_presets_for_provider,
)
from app.voice.business_logic.tts.cartesia_tts import CartesiaTTS
from app.voice.business_logic.tts.edge_neural_tts import EdgeNeuralTTS

_APP = QApplication.instance() or QApplication([])


class TestCustomVoicesAndTTS(unittest.TestCase):
    """Test suite verifying voice preset resolution, custom voices, and TTS settings."""

    def test_presets_by_provider(self):
        edge_voices = get_presets_for_provider("edge_neural_tts")
        self.assertTrue(len(edge_voices) >= 5)
        self.assertTrue(any(v_id == "bn-BD-NabanitaNeural" for _, v_id in edge_voices))
        self.assertTrue(any(v_id == "bn-BD-PradeepNeural" for _, v_id in edge_voices))

        cartesia_voices = get_presets_for_provider("cartesia")
        self.assertTrue(len(cartesia_voices) >= 2)
        self.assertTrue(any("2c8d7dfb" in v_id for _, v_id in cartesia_voices))

        elevenlabs_voices = get_presets_for_provider("elevenlabs")
        self.assertTrue(any(v_id == "EXAVITQu4vr4xnSDxMaL" for _, v_id in elevenlabs_voices))

    def test_custom_voices_merging(self):
        customs = [
            {"name": "My Personal Cloned Voice", "id": "custom-uuid-1234", "provider_id": "cartesia"},
            {"name": "Global Voice", "id": "global-id-5678", "provider_id": ""},
        ]
        cartesia_all = get_voices_for_provider("cartesia", customs)
        self.assertTrue(any(v_id == "custom-uuid-1234" for _, v_id in cartesia_all))
        self.assertTrue(any(v_id == "global-id-5678" for _, v_id in cartesia_all))

        # Should not include cartesia-specific custom voice in edge_neural_tts
        edge_all = get_voices_for_provider("edge_neural_tts", customs)
        self.assertFalse(any(v_id == "custom-uuid-1234" for _, v_id in edge_all))
        self.assertTrue(any(v_id == "global-id-5678" for _, v_id in edge_all))

    def test_voice_page_dynamic_dropdown_and_custom_voices(self):
        page = VoicePage()

        custom_voice = {"name": "Test Cloned Voice", "id": "test-uuid-9999", "provider_id": "cartesia"}
        schema = VoiceSettingsSchema(
            stt_provider_id="google_stt",
            tts_provider_id="cartesia",
            voice_id="test-uuid-9999",
            custom_voices=[custom_voice],
            language="bn",
        )
        page.load_settings(schema)

        out = page.get_settings()
        self.assertEqual(out.tts_provider_id, "cartesia")
        self.assertEqual(out.voice_id, "test-uuid-9999")
        self.assertEqual(len(out.custom_voices), 1)
        self.assertEqual(out.custom_voices[0]["id"], "test-uuid-9999")

        # Switching to edge_neural_tts should adapt voice dropdown
        idx = page.tts_combo.findData("edge_neural_tts")
        self.assertTrue(idx >= 0)
        page.tts_combo.setCurrentIndex(idx)

        edge_out = page.get_settings()
        self.assertEqual(edge_out.tts_provider_id, "edge_neural_tts")
        self.assertEqual(edge_out.voice_id, "bn-BD-NabanitaNeural")

    def test_cartesia_tts_402_quota_handling(self):
        cartesia = CartesiaTTS()
        with patch.object(cartesia, "_get_api_key", return_value="dummy_key"), \
             patch("requests.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 402
            mock_resp.text = "Model credits limit reached: Please upgrade your subscription"
            mock_post.return_value = mock_resp

            with self.assertRaises(RuntimeError) as ctx:
                cartesia.synthesise("নমস্কার", language="bn")

            self.assertIn("402 Quota Exceeded", str(ctx.exception))
            self.assertTrue(cartesia._quota_exceeded)

    def test_edge_neural_tts_custom_voices(self):
        edge = EdgeNeuralTTS()
        with patch("app.settings.settings_manager.SettingsManager.instance") as mock_mgr:
            mock_service = MagicMock()
            mock_service.schema.voice.voice_id = "bn-BD-PradeepNeural"
            mock_mgr.return_value.service = mock_service

            resolved = edge._resolve_voice(has_bengali=True, language="bn")
            self.assertEqual(resolved, "bn-BD-PradeepNeural")


if __name__ == "__main__":
    unittest.main()
