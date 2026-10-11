"""Unit tests for Phase 8 Settings AI Pages (Milestone 3)."""

import unittest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from app.settings.settings_schema import ProviderConfig, ModelConfig
from app.settings.ui.providers_page import ProvidersPage, ProviderCardWidget
from app.settings.ui.models_page import ModelsPage

_APP = QApplication.instance() or QApplication([])


class TestSettingsAIPages(unittest.TestCase):
    """Test suite for AI Providers, Connection Testing, and Model Task Role Mappings."""

    def test_provider_card_widget(self):
        card = ProviderCardWidget("openrouter", "OpenRouter", "https://openrouter.ai/api/v1")
        p_in = ProviderConfig(name="OpenRouter", enabled=True, api_key="sk-test-12345678", base_url="https://openrouter.ai/api/v1", status="active")
        card.load_config(p_in)

        self.assertTrue(card.enable_check.isChecked())
        self.assertEqual(card.key_edit.text(), "sk-test-12345678")

        p_out = card.get_config()
        self.assertEqual(p_out.name, "OpenRouter")
        self.assertTrue(p_out.enabled)
        self.assertEqual(p_out.api_key, "sk-test-12345678")

    def test_providers_page_load_and_get(self):
        page = ProvidersPage()
        providers_in = {
            "google_ai_studio": ProviderConfig(name="Google AI Studio", enabled=True, api_key="goog-key-12345"),
            "openrouter": ProviderConfig(name="OpenRouter", enabled=True, api_key="or-key-67890"),
        }
        page.load_settings(providers_in)

        res = page.get_settings()
        self.assertIn("google_ai_studio", res)
        self.assertEqual(res["google_ai_studio"].api_key, "goog-key-12345")
        self.assertIn("openrouter", res)
        self.assertEqual(res["openrouter"].api_key, "or-key-67890")
        self.assertIn("tavily", res)
        self.assertIn("brave_search", res)

    def test_web_search_provider_keys_round_trip(self):
        page = ProvidersPage()
        page.load_settings({
            "tavily": ProviderConfig(name="Tavily", enabled=True, api_key="tvly-test-key"),
            "brave_search": ProviderConfig(name="Brave Search", enabled=True, api_key="brave-test-key"),
        })

        settings = page.get_settings()
        self.assertEqual(settings["tavily"].api_key, "tvly-test-key")
        self.assertEqual(settings["brave_search"].api_key, "brave-test-key")

    def test_models_page_load_and_get(self):
        page = ModelsPage()
        m_in = ModelConfig(
            chat_model="deepseek/deepseek-chat",
            coding_model="anthropic/claude-3.5-sonnet",
            reasoning_model="deepseek/deepseek-r1",
            vision_model="openai/gpt-4o",
            voice_model="eleven_v3",
            image_model="openai/dall-e-3",
            fallback_model="meta-llama/llama-3.3-70b-instruct"
        )
        page.load_settings(m_in)

        m_out = page.get_settings()
        self.assertEqual(m_out.chat_model, "deepseek/deepseek-chat")
        self.assertEqual(m_out.coding_model, "anthropic/claude-3.5-sonnet")
        self.assertEqual(m_out.reasoning_model, "deepseek/deepseek-r1")
        self.assertEqual(m_out.vision_model, "openai/gpt-4o")
        self.assertEqual(m_out.fallback_model, "meta-llama/llama-3.3-70b-instruct")


if __name__ == "__main__":
    unittest.main()
