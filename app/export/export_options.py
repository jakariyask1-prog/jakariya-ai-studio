"""Shared, format-agnostic settings for a conversation export."""

from __future__ import annotations

import re
from dataclasses import dataclass


_FORMAT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._+-]*$")


@dataclass(frozen=True, slots=True)
class ExportOptions:
    """User-selected export settings passed unchanged to an exporter.

    ``format_id`` deliberately remains a string instead of a closed enum.
    This lets a future plugin add a format by registering an exporter without
    changing this shared contract.
    """

    format_id: str
    include_timestamps: bool = True
    include_metadata: bool = True
    include_attachments: bool = True
    include_images: bool = True
    copy_assets: bool = False
    content_only: bool = False
    message_ids: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        normalized_format = self.normalize_format_id(self.format_id)
        object.__setattr__(self, "format_id", normalized_format)

        if self.message_ids is not None:
            normalized_ids = tuple(message_id.strip() for message_id in self.message_ids)
            if not normalized_ids or any(not message_id for message_id in normalized_ids):
                raise ValueError("Selected message IDs cannot be empty.")
            object.__setattr__(self, "message_ids", normalized_ids)

    @staticmethod
    def normalize_format_id(format_id: str) -> str:
        """Return the canonical registry key for an export format."""
        normalized_format = format_id.strip().lower().lstrip(".")
        if not _FORMAT_ID_PATTERN.fullmatch(normalized_format):
            raise ValueError("Export format must be a non-empty, safe format identifier.")
        return normalized_format
