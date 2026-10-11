"""Provider Capabilities definition for Jakariya AI Studio."""

from dataclasses import dataclass


@dataclass
class ProviderCapabilities:
    """Functional AI capabilities supported by a provider."""
    supports_chat: bool = True
    supports_reasoning: bool = False
    supports_coding: bool = True
    supports_vision: bool = False
    supports_image_generation: bool = False
    supports_stt: bool = False
    supports_tts: bool = False
    supports_web_search: bool = False
