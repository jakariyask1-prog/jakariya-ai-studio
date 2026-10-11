"""Global SettingsManager singleton providing central configuration access across application modules."""

from __future__ import annotations

import logging
from typing import Any, Optional
from PySide6.QtCore import QObject

from app.settings.configuration_service import ConfigurationService
from app.settings.storage import SettingsStorage


class SettingsManager(QObject):
    """Application-wide singleton manager for accessing and updating configuration."""

    _instance: Optional[SettingsManager] = None

    def __init__(self, service: ConfigurationService | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        if SettingsManager._instance is not None and SettingsManager._instance != self:
            logging.warning("[SettingsManager] Multiple instances created. Prefer SettingsManager.instance().")
        self._service = service or ConfigurationService(SettingsStorage(), self)
        SettingsManager._instance = self

    @classmethod
    def instance(cls) -> SettingsManager:
        """Return the global SettingsManager singleton instance."""
        if cls._instance is None:
            cls._instance = SettingsManager()
        return cls._instance

    @property
    def service(self) -> ConfigurationService:
        """Return the underlying ConfigurationService instance."""
        return self._service

    # Convenience Delegation Methods
    def get_setting(self, section: str, key: str, default: Any = None) -> Any:
        return self._service.get_setting(section, key, default)

    def update_setting(self, section: str, key: str, value: Any) -> bool:
        return self._service.update_setting(section, key, value)

    def get_api_key(self, provider_id: str) -> str:
        return self._service.get_api_key(provider_id)

    def get_model(self, task_role: str = "chat_model") -> str:
        return self._service.get_model(task_role)

    def set_model(self, task_role: str, model_id: str) -> bool:
        return self._service.set_model(task_role, model_id)
