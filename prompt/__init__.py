"""Public prompt exports for the application."""

try:
    from .system_prompt import SYSTEM_PROMPT, get_system_prompt_with_time, LIVE_VOICE_SYSTEM_DIRECTIVE
    from .profile_prompt import PROFILE_PROMPT
except ImportError as exc:  # pragma: no cover - defensive fallback
    raise ImportError("Unable to load the system prompt from the prompt package.") from exc

__all__ = ["SYSTEM_PROMPT", "PROFILE_PROMPT", "get_system_prompt_with_time", "LIVE_VOICE_SYSTEM_DIRECTIVE"]