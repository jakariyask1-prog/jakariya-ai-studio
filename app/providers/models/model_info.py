"""Metadata definition for individual AI models."""

from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Model specifications and capabilities."""
    id: str
    name: str
    provider_id: str
    context_window: int = 4096
    max_output_tokens: int = 2048
    supports_vision: bool = False
    supports_reasoning: bool = False
    supports_web_search: bool = False
