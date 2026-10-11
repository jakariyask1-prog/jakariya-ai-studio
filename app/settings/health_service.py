"""Provider Health & Environment Checker Service for Jakariya AI Studio."""

from __future__ import annotations

from enum import Enum
from typing import Dict
from PySide6.QtCore import QObject

from app.settings.configuration_service import ConfigurationService
from app.settings.validators import validate_api_key


class HealthStatus(Enum):
    """Enumeration of provider health states."""
    READY = "Ready"            # Enabled with valid API key
    WARNING = "Warning"        # Disabled or non-critical notice
    ERROR = "Error"            # Invalid key format or malformed URL
    NO_API_KEY = "No API Key"  # Unconfigured / missing key


class ProviderHealthService(QObject):
    """Evaluates configuration health, credential presence, and status of AI providers."""

    def __init__(self, service: ConfigurationService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._service = service

    def evaluate_provider_health(self, provider_id: str) -> HealthStatus:
        """Evaluate and return the HealthStatus enum for provider_id."""
        p_conf = self._service.get_provider_config(provider_id)
        api_key = self._service.get_api_key(provider_id)

        if not api_key:
            return HealthStatus.NO_API_KEY

        if not validate_api_key(api_key):
            return HealthStatus.ERROR

        if not p_conf.enabled:
            return HealthStatus.WARNING

        return HealthStatus.READY

    def get_all_provider_health(self) -> Dict[str, HealthStatus]:
        """Return dictionary mapping provider_id to HealthStatus enum."""
        health_map = {}
        for p_id in self._service.schema.providers.keys():
            health_map[p_id] = self.evaluate_provider_health(p_id)
        return health_map
