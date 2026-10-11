"""Dynamic AI Model Catalog populated via ProviderRegistry and ProviderManager."""

from __future__ import annotations

from typing import List, Tuple
from app.providers.manager.provider_registry import ProviderRegistry
from app.providers.manager.provider_manager import ProviderManager

DEFAULT_MODEL = "deepseek/deepseek-chat"


def get_provider_options() -> List[Tuple[str, str]]:
    """Return list of (display_name, provider_id) tuples for all registered providers."""
    mgr = ProviderManager.instance()
    p_ids = mgr.list_providers()
    options = []
    for p_id in p_ids:
        meta = ProviderRegistry.get_provider_meta(p_id)
        name = meta.name if meta else p_id.replace("_", " ").title()
        options.append((name, p_id))
    return options


def get_model_options(provider_id: str | None = None) -> List[Tuple[str, str]]:
    """Return list of (display_name, model_id) tuples dynamically from ProviderRegistry / ProviderManager."""
    models = []
    if provider_id:
        models = ProviderRegistry.get_models_for_provider(provider_id)
    else:
        models = ProviderRegistry.get_all_models()

    if not models:
        mgr = ProviderManager.instance()
        if provider_id and mgr.get_provider(provider_id):
            models = mgr.get_provider(provider_id).get_supported_models()
        else:
            for p in mgr._providers.values():
                models.extend(p.get_supported_models())

    return [(m.name, m.id) for m in models]


# For backwards compatibility with static imports
MODEL_OPTIONS = tuple(get_model_options())
