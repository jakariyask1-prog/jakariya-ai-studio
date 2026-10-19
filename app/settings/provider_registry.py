"""Central AI Provider & Dynamic Model Capability Registry for Jakariya AI Studio."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict


@dataclass
class ProviderCapabilities:
    """Dataclass defining functional AI capabilities supported by a provider."""
    supports_chat: bool = True
    supports_reasoning: bool = False
    supports_coding: bool = True
    supports_vision: bool = False
    supports_image_generation: bool = False
    supports_stt: bool = False
    supports_tts: bool = False
    supports_web_search: bool = False


@dataclass
class ProviderMeta:
    """Metadata container for an AI Provider, including base URL, capabilities, and model catalog."""
    id: str
    name: str
    default_base_url: str
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    models: List[str] = field(default_factory=list)


class ProviderRegistry:
    """Central registry of AI Providers, capabilities, and dynamic model catalogs."""

    _PROVIDERS: Dict[str, ProviderMeta] = {
        "google_ai_studio": ProviderMeta(
            id="google_ai_studio",
            name="Google AI Studio (Gemini)",
            default_base_url="https://generativelanguage.googleapis.com",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_reasoning=True,
                supports_coding=True,
                supports_vision=True,
                supports_stt=True,
                supports_tts=True,
            ),
            models=[
                "google/gemini-2.5-pro",
                "google/gemini-2.0-flash",
                "google/gemini-2.0-flash-thinking-exp",
                "google/gemini-1.5-pro",
                "google/gemini-1.5-flash",
                "google/gemini-3.8-flash",
                "google/gemini-3.6-flash",
            ],
        ),
        "openrouter": ProviderMeta(
            id="openrouter",
            name="OpenRouter (Unified Multi-Model Gateway)",
            default_base_url="https://openrouter.ai/api/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_reasoning=True,
                supports_coding=True,
                supports_vision=True,
                supports_image_generation=True,
                supports_web_search=True,
            ),
            models=[
                "anthropic/claude-3.7-sonnet",
                "anthropic/claude-3.5-sonnet",
                "deepseek/deepseek-chat",
                "deepseek/deepseek-r1",
                "qwen/qwen-2.5-coder-32b-instruct",
                "meta-llama/llama-3.3-70b-instruct",
                "openai/gpt-4o",
                "openai/gpt-4o-mini",
                "qwen/qwen-2.5-72b-instruct",
            ],
        ),
        "groq": ProviderMeta(
            id="groq",
            name="Groq (Ultra High-Speed Engine)",
            default_base_url="https://api.groq.com/openai/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_reasoning=True,
                supports_coding=True,
                supports_vision=False,
            ),
            models=[
                "llama-3.3-70b-versatile",
                "qwen-2.5-coder-32b",
                "deepseek-r1-distill-llama-70b",
                "llama-3.1-8b-instant",
                "openai/gpt-oss-120b",
                "qwen/qwen3.8-27b",
            ],
        ),
        "cerebras": ProviderMeta(
            id="cerebras",
            name="Cerebras (Wafer-Scale AI)",
            default_base_url="https://api.cerebras.ai/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_coding=True,
                supports_reasoning=False,
            ),
            models=[
                "llama-3.3-70b",
                "llama3.1-8b",
                "qwen-3.8-27b",
                "gpt-oss-120b",
            ],
        ),
        "anthropic": ProviderMeta(
            id="anthropic",
            name="Anthropic (Claude)",
            default_base_url="https://api.anthropic.com/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_coding=True,
                supports_reasoning=True,
                supports_vision=True,
            ),
            models=[
                "anthropic/claude-3-7-sonnet",
                "anthropic/claude-3-5-sonnet",
                "anthropic/claude-3-5-haiku",
            ],
        ),
        "ollama": ProviderMeta(
            id="ollama",
            name="Ollama (Local Models)",
            default_base_url="http://localhost:11434/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_coding=True,
                supports_reasoning=True,
            ),
            models=[
                "ollama/llama3.1",
                "ollama/llama3.2",
                "ollama/qwen2.5",
                "ollama/deepseek-coder-v2",
            ],
        ),
        "plugsky": ProviderMeta(
            id="plugsky",
            name="Plugsky AI",
            default_base_url="https://api.plugsky.com/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_coding=True,
                supports_reasoning=True,
                supports_vision=True,
            ),
            models=[
                "plugsky-lite",
                "plugsky-micro",
                "plugsky-pro",
                "plugsky-reasoning",
                "plugsky-deepseek-pro",
            ],
        ),
        "mistral": ProviderMeta(
            id="mistral",
            name="Mistral AI Direct",
            default_base_url="https://api.mistral.ai/v1",
            capabilities=ProviderCapabilities(
                supports_chat=True,
                supports_coding=True,
                supports_reasoning=True,
                supports_vision=True,
            ),
            models=[
                "mistral-large-latest",
                "mistral-small-latest",
                "codestral-latest",
                "pixtral-large-latest",
            ],
        ),
    }

    @classmethod
    def get_provider_ids(cls) -> List[str]:
        """Return list of all registered provider identifiers."""
        return list(cls._PROVIDERS.keys())

    @classmethod
    def get_provider_meta(cls, provider_id: str) -> ProviderMeta | None:
        """Return metadata for provider_id if registered."""
        return cls._PROVIDERS.get(provider_id)

    @classmethod
    def get_models_for_provider(cls, provider_id: str) -> List[str]:
        """Return model catalog list for provider_id."""
        meta = cls.get_provider_meta(provider_id)
        return meta.models if meta else []

    @classmethod
    def get_all_models(cls) -> List[str]:
        """Return aggregated list of all models across all providers."""
        all_models = []
        for meta in cls._PROVIDERS.values():
            all_models.extend(meta.models)
        return all_models

    @classmethod
    def get_providers_for_capability(cls, capability_name: str) -> List[str]:
        """Return provider IDs supporting the specified capability attribute."""
        matching = []
        for p_id, meta in cls._PROVIDERS.items():
            if getattr(meta.capabilities, capability_name, False):
                matching.append(p_id)
        return matching
