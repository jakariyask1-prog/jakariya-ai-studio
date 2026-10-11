"""Unit tests verifying all 7 active Provider Connectors."""

import unittest
from app.providers.implementations.openrouter_provider import OpenRouterProvider
from app.providers.implementations.google_provider import GoogleAIStudioProvider
from app.providers.implementations.anthropic_provider import AnthropicProvider
from app.providers.implementations.groq_provider import GroqProvider
from app.providers.implementations.cerebras_provider import CerebrasProvider
from app.providers.implementations.ollama_provider import OllamaProvider
from app.providers.implementations.plugsky_provider import PlugskyProvider
from app.providers.implementations.mistral_provider import MistralProvider


class TestAllProviderConnectors(unittest.TestCase):
    """Test suite for all 8 AI Provider implementations."""

    def test_openrouter_provider_contract(self):
        p = OpenRouterProvider(api_key="sk-or-test-key")
        self.assertEqual(p.provider_id, "openrouter")
        self.assertTrue(p.validate_api_key())
        self.assertTrue(p.capabilities.supports_chat)
        self.assertTrue(p.capabilities.supports_reasoning)
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 5)
        model_ids = [m.id for m in models]
        self.assertIn("deepseek/deepseek-chat", model_ids)

    def test_google_provider_contract(self):
        p = GoogleAIStudioProvider(api_key="AIzaSyTestKey")
        self.assertEqual(p.provider_id, "google_ai_studio")
        self.assertTrue(p.validate_api_key())
        self.assertTrue(p.capabilities.supports_vision)
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 3)
        self.assertEqual(p._format_model_name("google/gemini-2.5-pro"), "gemini-2.5-pro")

    def test_anthropic_provider_contract(self):
        p = AnthropicProvider(api_key="sk-ant-api03-testkey")
        self.assertEqual(p.provider_id, "anthropic")
        self.assertTrue(p.validate_api_key())
        self.assertTrue(p.capabilities.supports_vision)
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 3)
        self.assertEqual(p._format_model_name("anthropic/claude-3.5-sonnet"), "claude-3-5-sonnet-20241022")

    def test_groq_provider_contract(self):
        p = GroqProvider(api_key="gsk_testkey12345")
        self.assertEqual(p.provider_id, "groq")
        self.assertTrue(p.validate_api_key())
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 3)
        self.assertEqual(p._format_model_name("groq/llama-3.3-70b-versatile"), "llama-3.3-70b-versatile")

    def test_cerebras_provider_contract(self):
        p = CerebrasProvider(api_key="csk-testkey12345")
        self.assertEqual(p.provider_id, "cerebras")
        self.assertTrue(p.validate_api_key())
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 2)
        self.assertEqual(p._format_model_name("cerebras/llama3.3-70b"), "llama3.3-70b")

    def test_ollama_provider_contract(self):
        p = OllamaProvider(api_key="not-needed")
        self.assertEqual(p.provider_id, "ollama")
        self.assertTrue(p.validate_api_key())
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 2)

    def test_plugsky_provider_contract(self):
        p = PlugskyProvider(api_key="sk-plugsky-testkey12345")
        self.assertEqual(p.provider_id, "plugsky")
        self.assertTrue(p.validate_api_key())
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 2)

    def test_mistral_provider_contract(self):
        p = MistralProvider(api_key="sk-mistral-testkey12345")
        self.assertEqual(p.provider_id, "mistral")
        self.assertTrue(p.validate_api_key())
        self.assertTrue(p.capabilities.supports_chat)
        self.assertTrue(p.capabilities.supports_coding)
        self.assertTrue(p.capabilities.supports_vision)
        models = p.get_supported_models()
        self.assertGreaterEqual(len(models), 4)
        model_ids = [m.id for m in models]
        self.assertIn("mistral-large-latest", model_ids)
        self.assertIn("codestral-latest", model_ids)
        self.assertEqual(p._format_model_name("mistral/mistral-large-latest"), "mistral-large-latest")


if __name__ == "__main__":
    unittest.main()
