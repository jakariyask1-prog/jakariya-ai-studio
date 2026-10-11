"""Helpers for exporting persisted image attachments and generated images."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.export.models import ExportMessage


_IMAGE_SOURCE_PATTERN = re.compile(r'<img[^>]+src=["\'](?P<source>[^"\']+)["\']', re.IGNORECASE)


def message_image_paths(message: ExportMessage) -> tuple[Path, ...]:
    """Return existing image files from attachments and generated-image markup."""
    candidates = [
        Path(attachment.stored_path)
        for attachment in message.attachments
        if attachment.is_image
    ]
    candidates.extend(_image_paths_from_markup(message.content))

    seen: set[Path] = set()
    images: list[Path] = []
    for candidate in candidates:
        try:
            path = candidate.resolve()
        except OSError:
            continue
        if path.is_file() and path not in seen:
            seen.add(path)
            images.append(path)
    return tuple(images)


def _image_paths_from_markup(content: str) -> tuple[Path, ...]:
    paths: list[Path] = []
    for match in _IMAGE_SOURCE_PATTERN.finditer(content):
        source = unquote(match.group("source"))
        parsed = urlparse(source)
        if parsed.scheme == "file":
            paths.append(Path(parsed.path.lstrip("/")))
        elif not parsed.scheme:
            paths.append(Path(source))
    return tuple(paths)
