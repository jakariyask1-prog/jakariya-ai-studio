"""Unit tests for dynamic Provider & Model loading in application Header."""

import os
import unittest
from PySide6.QtWidgets import QApplication
from app.ui.header import Header
from app.providers.manager.provider_manager import ProviderManager

_APP = QApplication.instance() or QApplication([])


class TestHeaderModelLoading(unittest.TestCase):
    """Test suite verifying dynamic Provider & Model loading in application Header UI."""

    def setUp(self):
        ProviderManager.reset_instance()
        self.mgr = ProviderManager.instance()

    def test_header_dynamic_provider_and_model_population(self):
        header = Header()

        # Check provider selector items
        provider_count = header.provider_selector.count()
        self.assertGreaterEqual(provider_count, 7)

        # Check default selected provider & model
        first_provider = header.selected_provider()
        self.assertTrue(bool(first_provider))

        models_count = header.model_selector.count()
        self.assertGreater(models_count, 0)

    def test_header_model_refresh_on_provider_change(self):
        header = Header()

        # Switch to Google AI Studio
        google_idx = -1
        for i in range(header.provider_selector.count()):
            if header.provider_selector.itemData(i) == "google_ai_studio":
                google_idx = i
                break

        self.assertNotEqual(google_idx, -1)
        header.provider_selector.setCurrentIndex(google_idx)

        # Verify model selector contains Google models
        selected_model = header.selected_model()
        self.assertIn("gemini", selected_model.lower())

        # Switch to Anthropic
        anthropic_idx = -1
        for i in range(header.provider_selector.count()):
            if header.provider_selector.itemData(i) == "anthropic":
                anthropic_idx = i
                break

        self.assertNotEqual(anthropic_idx, -1)
        header.provider_selector.setCurrentIndex(anthropic_idx)

        selected_model_anthropic = header.selected_model()
        self.assertIn("claude", selected_model_anthropic.lower())


if __name__ == "__main__":
    unittest.main()
