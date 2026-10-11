"""Configuration Service — single point of truth for application settings, signal broadcasting, and key resolution."""

from __future__ import annotations

import os
from typing import Any
from PySide6.QtCore import QObject, Signal, QMutex, QMutexLocker

from app.settings.settings_schema import AppSettingsSchema, ProviderConfig
from app.settings.storage import SettingsStorage


class ConfigurationService(QObject):
    """Central Configuration Service providing thread-safe settings access, key resolution, and Qt signals."""

    # PySide6 Signals
    setting_changed = Signal(str, str, object)  # section, key, value
    provider_updated = Signal(str, object)      # provider_id, ProviderConfig
    model_updated = Signal(str, str)            # task_role, model_id
    settings_reloaded = Signal()

    def __init__(self, storage: SettingsStorage | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._mutex = QMutex()
        self._storage = storage or SettingsStorage()
        self._settings_data: AppSettingsSchema = AppSettingsSchema()
        self.reload()

    def reload(self) -> None:
        """Reload settings from disk storage and emit reloaded signal."""
        QMutexLocker(self._mutex)
        raw_dict = self._storage.load()
        self._settings_data = AppSettingsSchema.from_dict(raw_dict)
        self.settings_reloaded.emit()

    def save(self) -> bool:
        """Save active settings to storage."""
        QMutexLocker(self._mutex)
        data_dict = self._settings_data.to_dict()
        return self._storage.save(data_dict)

    @property
    def schema(self) -> AppSettingsSchema:
        """Return reference to master AppSettingsSchema object."""
        return self._settings_data

    @schema.setter
    def schema(self, new_schema: AppSettingsSchema) -> None:
        """Set master AppSettingsSchema object with thread-safety."""
        QMutexLocker(self._mutex)
        if isinstance(new_schema, AppSettingsSchema):
            self._settings_data = new_schema

    def reset_defaults(self) -> bool:
        """Reset all configuration settings back to DEFAULT_SETTINGS in-memory only.

        The caller is responsible for calling save() if the reset should be persisted.
        This allows Cancel to rollback without the reset being committed to disk.
        """
        from app.settings.defaults import DEFAULT_SETTINGS
        QMutexLocker(self._mutex)
        self._settings_data = AppSettingsSchema.from_dict(DEFAULT_SETTINGS)
        self.settings_reloaded.emit()
        return True

    # ------------------------------------------------------------------
    # Generic Setting Access
    # ------------------------------------------------------------------

    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        """Get a setting value by section and key."""
        section_obj = getattr(self._settings_data, section, None)
        if section_obj is None:
            return default
        if isinstance(section_obj, dict):
            return section_obj.get(key, default)
        return getattr(section_obj, key, default)

    def update_setting(self, section: str, key: str, value: Any) -> bool:
        """Update a specific setting value, save to disk, and emit signal."""
        section_obj = getattr(self._settings_data, section, None)
        if section_obj is None:
            return False

        if isinstance(section_obj, dict):
            section_obj[key] = value
        else:
            if not hasattr(section_obj, key):
                return False
            setattr(section_obj, key, value)

        self.save()
        self.setting_changed.emit(section, key, value)
        return True

    # ------------------------------------------------------------------
    # Provider Management & API Key Resolution
    # ------------------------------------------------------------------

    def get_provider_config(self, provider_id: str) -> ProviderConfig:
        """Return ProviderConfig for provider_id or empty default."""
        return self._settings_data.providers.get(provider_id, ProviderConfig(name=provider_id))

    def update_provider_config(self, provider_id: str, config: ProviderConfig) -> bool:
        """Update configuration for provider_id, store API key in keyring, save, and emit signal."""
        from app.settings.key_vault import store_api_key, _is_keyring_available
        # Attempt to migrate key to keyring; scrub plaintext from config if successful
        if config.api_key and config.api_key not in ("", "__keyring__"):
            if _is_keyring_available() and store_api_key(provider_id, config.api_key):
                config = ProviderConfig(
                    name=config.name,
                    enabled=config.enabled,
                    api_key="__keyring__",
                    base_url=config.base_url,
                    status=config.status,
                    priority=config.priority,
                )
        self._settings_data.providers[provider_id] = config
        success = self.save()
        self.provider_updated.emit(provider_id, config)
        return success

    def get_api_key(self, provider_id: str) -> str:
        """Resolve API Key for provider_id.

        Order of resolution:
        1. Windows Credential Manager / keyring (if keyring is installed)
        2. Settings JSON file (plaintext fallback if keyring unavailable)
        3. Environment variables (.env fallback)
        """
        from app.settings.key_vault import retrieve_api_key

        # 1. Try keyring (Windows Credential Manager) first
        vault_key = retrieve_api_key(provider_id)
        if vault_key:
            return vault_key

        # 2. Plaintext JSON fallback (only when keyring is not available)
        p_conf = self.get_provider_config(provider_id)
        stored_key = p_conf.api_key or ""
        if stored_key and stored_key.strip() not in ("", "__keyring__"):
            return stored_key.strip()

        # 3. Environment variable fallback
        env_map = {
            "google_ai_studio": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "cerebras": "CEREBRAS_API_KEY",
            "ollama": "OLLAMA_API_KEY",
            "plugsky": "PLUGSKY_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "tavily": "TAVILY_API_KEY",
            "brave_search": "BRAVE_SEARCH_API_KEY",
            "stability_ai": "STABILITY_API_KEY",
            "cartesia": "CARTESIA_API_KEY",
            "fish_audio": "FISH_AUDIO_API_KEY",
            "mistral": "MISTRAL_API_KEY",
            "elevenlabs": "ELEVENLABS_API_KEY",
            "llamaparse": "LLAMAPARSE_API_KEY",
            "huggingface": "HUGGINGFACE_API_KEY",
        }
        env_var = env_map.get(provider_id, f"{provider_id.upper()}_API_KEY")
        return os.getenv(env_var, "").strip()

    # ------------------------------------------------------------------
    # AI Model Task Resolution
    # ------------------------------------------------------------------

    def get_model(self, task_role: str = "chat_model") -> str:
        """Return active model ID for specified task_role (e.g. chat_model, coding_model)."""
        models_obj = self._settings_data.models
        return getattr(models_obj, task_role, models_obj.chat_model)

    def set_model(self, task_role: str, model_id: str) -> bool:
        """Set active model ID for specified task_role and emit signal."""
        models_obj = self._settings_data.models
        if not hasattr(models_obj, task_role):
            return False
        setattr(models_obj, task_role, model_id)
        success = self.save()
        self.model_updated.emit(task_role, model_id)
        return success

    # ------------------------------------------------------------------
    # Backup, Restore & Priority Failover
    # ------------------------------------------------------------------

    def export_backup(self, output_path: str) -> bool:
        """Export current settings to file path."""
        return self._storage.export_backup(output_path)

    def import_backup(self, input_path: str) -> bool:
        """Import settings from file path, reload, and emit signal."""
        merged = self._storage.import_backup(input_path)
        if merged:
            self.reload()
            return True
        return False

    def get_next_available_provider(self, required_capability: str = "supports_chat") -> str | None:
        """Return the highest priority enabled provider that has an API key and supports required_capability.

        Returns None if no enabled provider is available.
        """
        from app.settings.provider_registry import ProviderRegistry

        candidates = []
        for p_id, p_conf in self._settings_data.providers.items():
            if not p_conf.enabled:
                continue
            api_key = self.get_api_key(p_id)
            if not api_key:
                continue

            meta = ProviderRegistry.get_provider_meta(p_id)
            if meta and getattr(meta.capabilities, required_capability, False):
                candidates.append((p_conf.priority, p_id))

        if not candidates:
            return None

        # Sort by priority ascending (priority 1 first)
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
