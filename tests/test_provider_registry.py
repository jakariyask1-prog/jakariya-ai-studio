"""Unit tests for ProviderRegistry, capabilities, and schema versioning (Step 1)."""

import unittest
from app.settings.provider_registry import ProviderRegistry, ProviderCapabilities
from app.settings.settings_schema import AppSettingsSchema
from app.settings.defaults import DEFAULT_SETTINGS


class TestProviderRegistry(unittest.TestCase):
    """Test suite for provider capabilities, dynamic model catalogs, and schema versioning."""

    def test_schema_versioning(self):
        self.assertEqual(DEFAULT_SETTINGS["schema_version"], "1.0.0")
        self.assertEqual(DEFAULT_SETTINGS["app_version"], "1.0.0")

        schema = AppSettingsSchema.from_dict(DEFAULT_SETTINGS)
        self.assertEqual(schema.schema_version, "1.0.0")
        self.assertEqual(schema.app_version, "1.0.0")

    def test_provider_registry_lookup(self):
        provider_ids = ProviderRegistry.get_provider_ids()
        self.assertEqual(len(provider_ids), 8)
        self.assertIn("google_ai_studio", provider_ids)
        self.assertIn("openrouter", provider_ids)
        self.assertIn("mistral", provider_ids)

        meta = ProviderRegistry.get_provider_meta("openrouter")
        self.assertIsNotNone(meta)
        self.assertTrue(meta.capabilities.supports_chat)
        self.assertTrue(meta.capabilities.supports_reasoning)

    def test_dynamic_models_by_provider(self):
        gemini_models = ProviderRegistry.get_models_for_provider("google_ai_studio")
        self.assertIn("google/gemini-3.8-flash", gemini_models)

        all_models = ProviderRegistry.get_all_models()
        self.assertGreater(len(all_models), 15)

    def test_capability_filtering(self):
        vision_providers = ProviderRegistry.get_providers_for_capability("supports_vision")
        self.assertIn("google_ai_studio", vision_providers)
        self.assertIn("openrouter", vision_providers)


if __name__ == "__main__":
    unittest.main()
