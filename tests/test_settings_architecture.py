"""Unit tests for Phase 8 Settings Architecture (Milestone 1)."""

import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from PySide6.QtCore import QCoreApplication

from app.settings.defaults import DEFAULT_SETTINGS
from app.settings.validators import validate_api_key, validate_url, validate_range, validate_option
from app.settings.storage import SettingsStorage
from app.settings.settings_schema import AppSettingsSchema, ProviderConfig, ModelConfig
from app.settings.configuration_service import ConfigurationService
from app.settings.settings_manager import SettingsManager

_APP = QCoreApplication.instance() or QCoreApplication([])


class TestSettingsArchitecture(unittest.TestCase):
    """Test suite for settings backend, schema, storage, and configuration service."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_file = Path(self.temp_dir.name) / "test_settings.json"
        self.storage = SettingsStorage(self.temp_file)
        self.service = ConfigurationService(storage=self.storage)
        self.manager = SettingsManager(service=self.service)
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

    def test_defaults_and_validators(self):
        self.assertIn("providers", DEFAULT_SETTINGS)
        self.assertIn("google_ai_studio", DEFAULT_SETTINGS["providers"])
        self.assertIn("openrouter", DEFAULT_SETTINGS["providers"])

        self.assertTrue(validate_api_key("sk-or-v1-abcdef123456"))
        self.assertFalse(validate_api_key("short"))

        self.assertTrue(validate_url("https://openrouter.ai/api/v1"))
        self.assertFalse(validate_url("invalid-url"))

        self.assertEqual(validate_range(0.5, 0.0, 2.0), 0.5)
        self.assertEqual(validate_range(3.5, 0.0, 2.0), 2.0)

        self.assertEqual(validate_option("dark", ("dark", "light"), "dark"), "dark")
        self.assertEqual(validate_option("invalid", ("dark", "light"), "dark"), "dark")

    def test_storage_save_and_load(self):
        data = self.storage.load()
        self.assertEqual(data["general"]["language"], "en")
        self.assertEqual(data["appearance"]["theme"], "light")

        data["general"]["language"] = "bn"
        self.assertTrue(self.storage.save(data))

        reloaded = self.storage.load()
        self.assertEqual(reloaded["general"]["language"], "bn")

    def test_corrupt_settings_uses_a_unique_backup_name(self):
        self.temp_file.write_text("not valid json", encoding="utf-8")
        original_backup = self.temp_file.with_suffix(".json.bak")
        original_backup.write_text("older backup", encoding="utf-8")

        self.storage.load()

        backups = list(self.temp_file.parent.glob("test_settings.*.json.bak"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "not valid json")
        self.assertEqual(original_backup.read_text(encoding="utf-8"), "older backup")

    def test_schema_serialization(self):
        raw = self.storage.load()
        schema = AppSettingsSchema.from_dict(raw)
        self.assertEqual(schema.general.language, "en")

        self.assertIn("google_ai_studio", schema.providers)
        self.assertTrue(schema.providers["google_ai_studio"].enabled)

        serialized = schema.to_dict()
        self.assertIsInstance(serialized, dict)
        self.assertEqual(serialized["general"]["language"], "en")

    def test_configuration_service_and_signals(self):
        changed_signal_data = []

        def on_change(sec, key, val):
            changed_signal_data.append((sec, key, val))

        self.service.setting_changed.connect(on_change)

        self.assertTrue(self.service.update_setting("appearance", "theme", "light"))
        self.assertEqual(self.service.get_setting("appearance", "theme"), "light")
        self.assertEqual(len(changed_signal_data), 1)
        self.assertEqual(changed_signal_data[0], ("appearance", "theme", "light"))

    def test_provider_key_resolution(self):
        p_config = ProviderConfig(
            name="OpenRouter",
            enabled=True,
            api_key="sk-test-key-12345678",
            base_url="https://openrouter.ai/api/v1",
            status="active"
        )
        self.service.update_provider_config("openrouter", p_config)

        resolved_key = self.service.get_api_key("openrouter")
        self.assertEqual(resolved_key, "sk-test-key-12345678")

    def test_web_search_key_resolution(self):
        self.service.update_provider_config("tavily", ProviderConfig(api_key="tvly-settings-key"))
        self.service.update_provider_config("brave_search", ProviderConfig(api_key="brave-settings-key"))

        self.assertEqual(self.service.get_api_key("tavily"), "tvly-settings-key")
        self.assertEqual(self.service.get_api_key("brave_search"), "brave-settings-key")

    def test_plugsky_key_resolution_from_env(self):
        os.environ["PLUGSKY_API_KEY"] = "sk-plugsky-testkey"
        self.service.update_provider_config("plugsky", ProviderConfig(api_key=""))
        try:
            with unittest.mock.patch("app.settings.key_vault.retrieve_api_key", return_value=None), \
                 unittest.mock.patch("app.utils.paths.load_environment"):
                resolved_key = self.service.get_api_key("plugsky")
                self.assertEqual(resolved_key, "sk-plugsky-testkey")
        finally:
            del os.environ["PLUGSKY_API_KEY"]

    def test_settings_manager_singleton(self):
        singleton_mgr = SettingsManager.instance()
        self.assertIsNotNone(singleton_mgr)
        self.assertEqual(self.manager.get_model("chat_model"), "deepseek/deepseek-chat")

    def test_reset_defaults_and_schema_setter(self):
        self.service.update_setting("appearance", "theme", "neon")
        self.assertEqual(self.service.get_setting("appearance", "theme"), "neon")

        # Test reset defaults
        self.assertTrue(self.service.reset_defaults())
        self.assertEqual(self.service.get_setting("appearance", "theme"), "light")

        # Test schema setter
        new_schema = AppSettingsSchema.from_dict(DEFAULT_SETTINGS)
        self.service.schema = new_schema
        self.assertEqual(self.service.schema.appearance.theme, "light")


if __name__ == "__main__":
    unittest.main()
