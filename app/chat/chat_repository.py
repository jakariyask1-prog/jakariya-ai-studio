"""SQLite CRUD operations for conversations and messages.

This class deliberately contains no UI behaviour or chat rules.  Those belong
to ``ChatManager``; this repository only persists and retrieves domain data.
"""

from __future__ import annotations

from uuid import uuid4
from collections.abc import Sequence

from app.database.database import DatabaseManager, database
from app.models.attachment import Attachment, AttachmentInput
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole


class ChatRepository:
    """Persist conversations and messages using the application's SQLite store."""

    def __init__(self, db: DatabaseManager = database) -> None:
        self._db = db

    # Conversations -----------------------------------------------------

    def create_conversation(
        self,
        title: str = "New Chat",
        conversation_id: str | None = None,
    ) -> Conversation:
        """Create and return a conversation with a stable UUID."""
        new_id = conversation_id or str(uuid4())
        self._db.execute(
            "INSERT INTO conversations (id, title) VALUES (?, ?)",
            (new_id, title),
        )
        conversation = self.get_conversation(new_id)
        if conversation is None:  # Defensive guard for unexpected database failures.
            raise RuntimeError("Conversation was created but could not be loaded.")
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        """Return one conversation, or ``None`` if it does not exist."""
        row = self._db.fetch_one(
            "SELECT id, title, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        return Conversation.from_row(row) if row else None

    def list_conversations(self) -> list[Conversation]:
        """Return conversations with most recently updated first."""
        rows = self._db.fetch_all(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            ORDER BY last_message_rowid DESC, updated_at DESC, rowid DESC
            """
        )
        return [Conversation.from_row(row) for row in rows]

    def search_conversations(self, search_text: str) -> list[Conversation]:
        """Find conversations by title, treating search characters literally."""
        escaped_text = (
            search_text.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        rows = self._db.fetch_all(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE title LIKE ? ESCAPE '\\'
            ORDER BY last_message_rowid DESC, updated_at DESC, rowid DESC
            """,
            (f"%{escaped_text}%",),
        )
        return [Conversation.from_row(row) for row in rows]

    def rename_conversation(self, conversation_id: str, title: str) -> bool:
        """Update a conversation title; return whether a row was changed."""
        cursor = self._db.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, conversation_id),
        )
        return cursor.rowcount > 0

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and its messages through the cascade rule."""
        cursor = self._db.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        return cursor.rowcount > 0

    # Messages ----------------------------------------------------------

    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        message_id: str | None = None,
        attachments: Sequence[AttachmentInput] = (),
    ) -> Message:
        """Store a message and its attachment metadata as one operation."""
        new_id = message_id or str(uuid4())
        if attachments and role != "user":
            raise ValueError("Only user messages can have file attachments.")

        with self._db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content)
                VALUES (?, ?, ?, ?)
                """,
                (new_id, conversation_id, role, content),
            )
            connection.executemany(
                """
                INSERT INTO attachments (
                    id, message_id, original_name, stored_path, extension,
                    size_bytes, media_type, is_image
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid4()),
                        new_id,
                        attachment.original_name,
                        attachment.stored_path,
                        attachment.extension,
                        attachment.size_bytes,
                        attachment.media_type,
                        int(attachment.is_image),
                    )
                    for attachment in attachments
                ],
            )
        message = self.get_message(new_id)
        if message is None:  # Defensive guard for unexpected database failures.
            raise RuntimeError("Message was created but could not be loaded.")
        return message

    def list_attachments(self, message_id: str) -> list[Attachment]:
        """Return a message's attachments in the order they were added."""
        rows = self._db.fetch_all(
            """
            SELECT id, message_id, original_name, stored_path, extension,
                   size_bytes, media_type, is_image, created_at
            FROM attachments
            WHERE message_id = ?
            ORDER BY rowid ASC
            """,
            (message_id,),
        )
        return [Attachment.from_row(row) for row in rows]

    def list_conversation_attachments(self, conversation_id: str) -> dict[str, list[Attachment]]:
        """Group all persisted attachment metadata by message ID."""
        rows = self._db.fetch_all(
            """
            SELECT attachments.id, attachments.message_id, attachments.original_name,
                   attachments.stored_path, attachments.extension, attachments.size_bytes,
                   attachments.media_type, attachments.is_image, attachments.created_at
            FROM attachments
            INNER JOIN messages ON messages.id = attachments.message_id
            WHERE messages.conversation_id = ?
            ORDER BY messages.created_at ASC, messages.rowid ASC, attachments.rowid ASC
            """,
            (conversation_id,),
        )
        grouped: dict[str, list[Attachment]] = {}
        for row in rows:
            attachment = Attachment.from_row(row)
            grouped.setdefault(attachment.message_id, []).append(attachment)
        return grouped

    def get_message(self, message_id: str) -> Message | None:
        """Return one message, or ``None`` if it does not exist."""
        row = self._db.fetch_one(
            """
            SELECT id, conversation_id, role, content, created_at
            FROM messages
            WHERE id = ?
            """,
            (message_id,),
        )
        return Message.from_row(row) if row else None

    def list_messages(self, conversation_id: str) -> list[Message]:
        """Return a conversation's messages in their original order."""
        rows = self._db.fetch_all(
            """
            SELECT id, conversation_id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (conversation_id,),
        )
        return [Message.from_row(row) for row in rows]

    def delete_message(self, message_id: str) -> bool:
        """Delete one message; return whether it existed."""
        cursor = self._db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        return cursor.rowcount > 0

    def list_all_stored_paths(self) -> list[str]:
        """Return every stored_path recorded across all attachments.

        Used at startup to compute the set of files the database still knows
        about, so the orphan sweep can safely remove anything not in this set.
        """
        rows = self._db.fetch_all("SELECT stored_path FROM attachments")
        return [row["stored_path"] for row in rows]
