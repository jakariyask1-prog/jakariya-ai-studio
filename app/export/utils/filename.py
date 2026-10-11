"""Safe, user-friendly filenames for export and code-download actions."""

from __future__ import annotations

import re


_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{number}" for number in range(1, 10)), *(f"LPT{number}" for number in range(1, 10))}
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def build_filename(stem: str, extension: str, fallback: str = "export") -> str:
    """Return a portable filename, preserving a single requested extension."""
    clean_stem = _INVALID_FILENAME_CHARS.sub("-", stem).strip(" .")
    if not clean_stem or clean_stem.upper() in _WINDOWS_RESERVED:
        clean_stem = fallback
    clean_stem = clean_stem[:120].rstrip(" .") or fallback
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return f"{clean_stem}{normalized_extension.lower()}"
