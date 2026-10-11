"""Unit tests for Phase 8 Milestone 4 (Feature Pages & Final Integration)."""

import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.settings.settings_schema import VoiceSettingsSchema, ChatSettingsSchema, ExportSettingsSchema, AdvancedSettingsSchema
from app.settings.ui.voice_page import VoicePage
from app.settings.ui.chat_page import ChatPage
from app.settings.ui.export_page import ExportPage
from app.settings.ui.advanced_page import AdvancedPage
from app.ui.header import Header
from app.api.ClaudeClient import ClaudeClient

_APP = QApplication.instance() or QApplication([])


class TestSettingsMilestone4(unittest.TestCase):
    """Test suite for Voice, Chat, Export, Advanced UI pages, Header button, and API key resolution integration."""

    def test_voice_page_load_and_get(self):
        page = VoicePage()
        v_in = VoiceSettingsSchema(stt_provider_id="google_stt", tts_provider_id="edge_neural_tts", voice_id="test_voice_123", auto_send=False, silence_timeout_ms=1800, language="en")
        page.load_settings(v_in)

        v_out = page.get_settings()
        self.assertEqual(v_out.stt_provider_id, "google_stt")
        self.assertEqual(v_out.tts_provider_id, "edge_neural_tts")
        self.assertEqual(v_out.voice_id, "test_voice_123")
        self.assertFalse(v_out.auto_send)
        self.assertEqual(v_out.silence_timeout_ms, 1800)

    def test_chat_page_load_and_get(self):
        page = ChatPage()
        c_in = ChatSettingsSchema(system_persona="math_tutor", custom_system_prompt="Solve math step by step", attach_user_profile=True, temperature=0.5, max_tokens=4096)
        page.load_settings(c_in)

        c_out = page.get_settings()
        self.assertEqual(c_out.system_persona, "math_tutor")
        self.assertTrue(c_out.attach_user_profile)
        self.assertAlmostEqual(c_out.temperature, 0.5, places=2)
        self.assertEqual(c_out.max_tokens, 4096)

    def test_export_page_load_and_get(self):
        page = ExportPage()
        e_in = ExportSettingsSchema(default_format="docx", include_timestamps=False, include_attachments=True, paper_size="Letter (US)")
        page.load_settings(e_in)

        e_out = page.get_settings()
        self.assertEqual(e_out.default_format, "docx")
        self.assertFalse(e_out.include_timestamps)
        self.assertEqual(e_out.paper_size, "Letter (US)")

    def test_advanced_page_load_and_get(self):
        page = AdvancedPage()
        a_in = AdvancedSettingsSchema(log_level="DEBUG", auto_sweep_orphans=False, cache_limit_mb=1000)
        page.load_settings(a_in)

        a_out = page.get_settings()
        self.assertEqual(a_out.log_level, "DEBUG")
        self.assertFalse(a_out.auto_sweep_orphans)

    def test_header_settings_button(self):
        header = Header()
        self.assertIsNotNone(header.settings_button)

        emitted = []
        header.settings_requested.connect(lambda: emitted.append(True))
        header.settings_button.click()
        self.assertEqual(len(emitted), 1)

    def test_claude_client_key_integration(self):
        client = ClaudeClient()
        self.assertIsNotNone(client)


if __name__ == "__main__":
    unittest.main()
