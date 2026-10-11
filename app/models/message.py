"""Message domain model."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal


MessageRole = Literal["user", "assistant", "system"]


@dataclass(frozen=True, slots=True)
class Message:
    id: str
    conversation_id: str
    role: MessageRole
    content: str
    created_at: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Message":
        return cls(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            created_at=row["created_at"],
        )
