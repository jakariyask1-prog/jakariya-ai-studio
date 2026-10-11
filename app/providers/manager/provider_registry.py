"""Central Provider & Model Capabilities Registry for Phase 7 Provider Ecosystem."""

from typing import Dict, List, Optional
from app.providers.base.provider_capabilities import ProviderCapabilities
from app.providers.models.model_info import ModelInfo


class ProviderMeta:
    """Metadata container for an AI Provider."""

    def __init__(
        self,
        id: str,
        name: str,
        default_base_url: str,
        capabilities: ProviderCapabilities,
        models: List[ModelInfo],
    ):
        self.id = id
        self.name = name
        self.default_base_url = default_base_url
        self.capabilities = capabilities
        self.models = models


class ProviderRegistry:
    """Registry maintaining metadata, capabilities, and model catalogs for all 8 providers."""

    _PROVIDERS: Dict[str, ProviderMeta] = {}

    @classmethod
    def register_provider(cls, meta: ProviderMeta) -> None:
        """Register provider metadata."""
        cls._PROVIDERS[meta.id] = meta

    @classmethod
    def get_provider_ids(cls) -> List[str]:
        """Return list of registered provider IDs."""
        return list(cls._PROVIDERS.keys())

    @classmethod
    def get_provider_meta(cls, provider_id: str) -> Optional[ProviderMeta]:
        """Return ProviderMeta for a given provider ID."""
        return cls._PROVIDERS.get(provider_id)

    @classmethod
    def get_models_for_provider(cls, provider_id: str) -> List[ModelInfo]:
        """Return supported model list for a given provider ID."""
        meta = cls.get_provider_meta(provider_id)
        return meta.models if meta else []

    @classmethod
    def get_all_models(cls) -> List[ModelInfo]:
        """Return list of all models across all registered providers."""
        all_models: List[ModelInfo] = []
        for meta in cls._PROVIDERS.values():
            all_models.extend(meta.models)
        return all_models

    @classmethod
    def clear(cls) -> None:
        """Clear registry entries (useful for testing)."""
        cls._PROVIDERS.clear()
