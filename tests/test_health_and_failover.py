"""Unit tests for ProviderHealthService, Backup/Restore, and Failover Resolution (Step 2)."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QCoreApplication

from app.settings.storage import SettingsStorage
from app.settings.configuration_service import ConfigurationService
from app.settings.health_service import ProviderHealthService, HealthStatus
from app.settings.settings_schema import ProviderConfig

_APP = QCoreApplication.instance() or QCoreApplication([])


class TestHealthAndFailover(unittest.TestCase):
    """Test suite for provider health evaluation, backup/restore, and priority failover resolution."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = Path(self.temp_dir.name) / "test_settings.json"
        self.storage = SettingsStorage(self.temp_file)
        self.service = ConfigurationService(storage=self.storage)
        self.health_service = ProviderHealthService(self.service)
        self._fake_keyring = {}
        self._patch_store = unittest.mock.patch(
            "app.settings.key_vault.store_api_key",
            side_effect=lambda pid, k: self._fake_keyring.__setitem__(pid, k) or True,
        )
        self._patch_retrieve = unittest.mock.patch(
            "app.settings.key_vault.retrieve_api_key",
            side_effect=lambda pid: self._fake_keyring.get(pid),
        )
        self._patch_store.start()
        self._patch_retrieve.start()

    def tearDown(self):
        self._patch_store.stop()
        self._patch_retrieve.stop()
        self.temp_dir.cleanup()

    @patch.dict(os.environ, {}, clear=True)
    def test_provider_health_evaluation(self):
        # Unconfigured provider (no key) -> NO_API_KEY
        status = self.health_service.evaluate_provider_health("google_ai_studio")
        self.assertEqual(status, HealthStatus.NO_API_KEY)

        # Set valid key & enable -> READY
        p_conf = ProviderConfig(name="Google AI Studio", enabled=True, api_key="sk-goog-12345678", priority=1)
        self.service.update_provider_config("google_ai_studio", p_conf)
        status_ready = self.health_service.evaluate_provider_health("google_ai_studio")
        self.assertEqual(status_ready, HealthStatus.READY)

        # Disable provider -> WARNING
        p_conf_disabled = ProviderConfig(name="Google AI Studio", enabled=False, api_key="sk-goog-12345678", priority=1)
        self.service.update_provider_config("google_ai_studio", p_conf_disabled)
        status_warn = self.health_service.evaluate_provider_health("google_ai_studio")
        self.assertEqual(status_warn, HealthStatus.WARNING)

    def test_backup_and_restore(self):
        backup_path = Path(self.temp_dir.name) / "backup_export.json"
        self.service.update_setting("appearance", "theme", "neon")

        # Export backup
        self.assertTrue(self.service.export_backup(str(backup_path)))
        self.assertTrue(backup_path.exists())

        # Modify active theme
        self.service.update_setting("appearance", "theme", "light")
        self.assertEqual(self.service.get_setting("appearance", "theme"), "light")

        # Restore from backup
        self.assertTrue(self.service.import_backup(str(backup_path)))
        self.assertEqual(self.service.get_setting("appearance", "theme"), "neon")

    def test_priority_failover_resolution(self):
        # Configure Provider 1 (Google, Priority 1, Disabled)
        p1 = ProviderConfig(name="Google AI Studio", enabled=False, api_key="sk-goog-12345678", priority=1)
        self.service.update_provider_config("google_ai_studio", p1)

        # Configure Provider 2 (OpenRouter, Priority 2, Enabled)
        p2 = ProviderConfig(name="OpenRouter", enabled=True, api_key="sk-or-12345678", priority=2)
        self.service.update_provider_config("openrouter", p2)

        # Failover should skip disabled Provider 1 and select Provider 2
        next_p = self.service.get_next_available_provider("supports_chat")
        self.assertEqual(next_p, "openrouter")


if __name__ == "__main__":
    unittest.main()
