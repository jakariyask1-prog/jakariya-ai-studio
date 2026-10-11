"""Abstract Base Provider Interface for all AI Providers."""

from abc import ABC, abstractmethod
from typing import Generator, List, Optional
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse, StreamChunk
from app.providers.models.model_info import ModelInfo


class BaseProvider(ABC):
    """Abstract Base Class enforcing standard interface across all AI providers."""

    def __init__(
        self,
        provider_id: str,
        name: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.provider_id = provider_id
        self.name = name
        self._explicit_api_key = api_key
        self._explicit_base_url = base_url

    @property
    def api_key(self) -> Optional[str]:
        if self._explicit_api_key and self._explicit_api_key.strip():
            return self._explicit_api_key.strip()
        try:
            from app.settings.settings_manager import SettingsManager
            cfg_key = SettingsManager.instance().service.get_api_key(self.provider_id)
            if cfg_key and cfg_key.strip():
                return cfg_key.strip()
        except Exception:
            pass
        return self._explicit_api_key

    @api_key.setter
    def api_key(self, val: Optional[str]) -> None:
        self._explicit_api_key = val

    @property
    def base_url(self) -> Optional[str]:
        if self._explicit_base_url and self._explicit_base_url.strip():
            return self._explicit_base_url.strip()
        try:
            from app.settings.settings_manager import SettingsManager
            p_conf = SettingsManager.instance().service.get_provider_config(self.provider_id)
            if p_conf.base_url and p_conf.base_url.strip():
                return p_conf.base_url.strip()
        except Exception:
            pass
        return self._explicit_base_url

    @base_url.setter
    def base_url(self, val: Optional[str]) -> None:
        self._explicit_base_url = val

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return provider capabilities."""

    @abstractmethod
    def get_supported_models(self) -> List[ModelInfo]:
        """Return list of supported ModelInfo objects."""

    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate if configured API key is present and structurally valid."""

    @abstractmethod
    def chat(self, request: ChatRequest) -> ChatResponse:
        """Send non-streaming chat request."""

    @abstractmethod
    def chat_stream(self, request: ChatRequest) -> Generator[StreamChunk, None, None]:
        """Send streaming chat request yielding StreamChunk instances."""
