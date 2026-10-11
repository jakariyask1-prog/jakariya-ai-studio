"""Provider Health Monitoring Service."""

from enum import Enum
from typing import Optional


class HealthStatus(str, Enum):
    READY = "ready"
    NO_API_KEY = "no_api_key"
    DISABLED = "disabled"
    ERROR = "error"


class ProviderHealthService:
    """Evaluates health and operational status of providers."""

    @staticmethod
    def evaluate_status(api_key: Optional[str], enabled: bool = True) -> HealthStatus:
        if not enabled:
            return HealthStatus.DISABLED
        if not api_key or not api_key.strip():
            return HealthStatus.NO_API_KEY
        return HealthStatus.READY
