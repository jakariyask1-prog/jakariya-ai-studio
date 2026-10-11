"""Domain models for files attached to user messages."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttachmentInput:
    """Validated attachment data before it is persisted with a message."""

    original_name: str
    stored_path: str
    extension: str
    size_bytes: int
    media_type: str = ""
    is_image: bool = False


@dataclass(frozen=True, slots=True)
class Attachment:
    """A persisted file attachment belonging to one chat message."""

    id: str
    message_id: str
    original_name: str
    stored_path: str
    extension: str
    size_bytes: int
    media_type: str
    is_image: bool
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Attachment":
        return cls(
            id=row["id"],
            message_id=row["message_id"],
            original_name=row["original_name"],
            stored_path=row["stored_path"],
            extension=row["extension"],
            size_bytes=row["size_bytes"],
            media_type=row["media_type"],
            is_image=bool(row["is_image"]),
            created_at=row["created_at"],
        )
