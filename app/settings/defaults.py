"""Centralized default configuration dictionary for Jakariya AI Studio settings."""

from __future__ import annotations

from typing import Any

DEFAULT_SETTINGS: dict[str, Any] = {
    "schema_version": "1.0.0",
    "app_version": "1.0.0",
    "general": {
        "language": "en",
        "auto_startup": False,
        "notifications_enabled": True,
        "user_age": 0,
    },
    "appearance": {
        "theme": "light",  # options: light, dark, oled, neon
        "font_family": "Segoe UI",
        "font_scale": 1.0,  # multiplier: 0.8 to 1.4
        "message_density": "comfortable",  # options: compact, comfortable
    },
    "providers": {
        "google_ai_studio": {
            "name": "Google AI Studio",
            "enabled": True,
            "api_key": "",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "status": "not_configured",
            "priority": 1,
        },
        "openrouter": {
            "name": "OpenRouter",
            "enabled": True,
            "api_key": "",
            "base_url": "https://openrouter.ai/api/v1",
            "status": "not_configured",
            "priority": 2,
        },
        "groq": {
            "name": "Groq",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.groq.com/openai/v1",
            "status": "not_configured",
        },
        "cerebras": {
            "name": "Cerebras",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.cerebras.ai/v1",
            "status": "not_configured",
        },
        "anthropic": {
            "name": "Anthropic",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.anthropic.com/v1",
            "status": "not_configured",
        },
        "ollama": {
            "name": "Ollama",
            "enabled": False,
            "api_key": "",
            "base_url": "http://localhost:11434/v1",
            "status": "not_configured",
        },
        "plugsky": {
            "name": "Plugsky AI",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.plugsky.com/v1",
            "status": "not_configured",
        },
        "stability_ai": {
            "name": "Stability AI Image (Optional)",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.stability.ai/v1",
            "status": "not_configured",
        },
        "tavily": {
            "name": "Tavily Web Search",
            "enabled": True,
            "api_key": "",
            "base_url": "https://api.tavily.com",
            "status": "not_configured",
        },
        "brave_search": {
            "name": "Brave Search API",
            "enabled": True,
            "api_key": "",
            "base_url": "https://api.search.brave.com/res/v1",
            "status": "not_configured",
        },
        "cartesia": {
            "name": "Cartesia AI Voice (Optional)",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.cartesia.ai",
            "status": "not_configured",
        },
        "fish_audio": {
            "name": "Fish Audio Voice (Optional)",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.fish.audio/v1",
            "status": "not_configured",
        },
        "mistral": {
            "name": "Mistral AI",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.mistral.ai/v1",
            "status": "not_configured",
        },
        "elevenlabs": {
            "name": "ElevenLabs Voice",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.elevenlabs.io/v1",
            "status": "not_configured",
        },
        "llamaparse": {
            "name": "LlamaParse Document Parser",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api.cloud.llamaindex.ai/api/v1",
            "status": "not_configured",
        },
        "huggingface": {
            "name": "Hugging Face",
            "enabled": False,
            "api_key": "",
            "base_url": "https://api-inference.huggingface.co",
            "status": "not_configured",
        },
    },
    "models": {
        "chat_model": "deepseek/deepseek-chat",
        "coding_model": "deepseek/deepseek-chat",
        "reasoning_model": "deepseek/deepseek-r1",
        "vision_model": "openai/gpt-4o",
        "voice_model": "edge_neural_tts",
        "image_model": "openai/dall-e-3",
        "fallback_model": "deepseek/deepseek-chat",
    },
    "voice": {
        "stt_provider_id": "google_stt",
        "tts_provider_id": "edge_neural_tts",
        "voice_id": "bn-BD-NabanitaNeural",
        "auto_send": True,
        "voice_response": True,
        "silence_timeout_ms": 1300,
        "vad_threshold": 0.008,
        "language": "bn",
    },
    "chat": {
        "system_persona": "default",
        "custom_system_prompt": "",
        "attach_user_profile": True,
        "max_history_turns": 20,
        "temperature": 0.7,
        "max_tokens": 2048,
    },
    "export": {
        "default_format": "pdf",
        "include_timestamps": True,
        "include_attachments": True,
        "paper_size": "A4",
    },
    "advanced": {
        "log_level": "INFO",
        "auto_sweep_orphans": True,
        "cache_limit_mb": 500,
    },
    "about": {
        "app_name": "Jakariya AI Studio",
        "version": "1.0.0",
        "creator": "Md. Jakariya Sheikh",
    },
}
