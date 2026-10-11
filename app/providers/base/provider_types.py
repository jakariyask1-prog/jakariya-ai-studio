"""Enums and type aliases for Provider Ecosystem."""

from enum import Enum


class ProviderId(str, Enum):
    OPENROUTER = "openrouter"
    GOOGLE = "google_ai_studio"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    PLUGSKY = "plugsky"


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
