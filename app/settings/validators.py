"""Validation functions for settings values, API keys, URLs, and numerical ranges."""

from __future__ import annotations

import re
from typing import Any


def validate_api_key(api_key: str) -> bool:
    """Return True if the API key string is non-empty and formatted cleanly."""
    if not isinstance(api_key, str):
        return False
    cleaned = api_key.strip()
    return len(cleaned) >= 8


def validate_url(url: str) -> bool:
    """Return True if url is a valid http or https URL."""
    if not isinstance(url, str) or not url.strip():
        return False
    pattern = r"^https?://[^\s/$.?#].[^\s]*$"
    return bool(re.match(pattern, url.strip(), re.IGNORECASE))


def validate_range(val: float | int, min_val: float | int, max_val: float | int) -> float | int:
    """Clamp a numerical value within [min_val, max_val]."""
    try:
        num = float(val)
        clamped = max(float(min_val), min(float(max_val), num))
        return int(clamped) if isinstance(min_val, int) and isinstance(max_val, int) else clamped
    except (ValueError, TypeError):
        return min_val


def validate_option(val: Any, valid_options: tuple[Any, ...], default_val: Any) -> Any:
    """Return val if present in valid_options, otherwise return default_val."""
    return val if val in valid_options else default_val
