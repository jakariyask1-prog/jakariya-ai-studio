"""Versioned SQLite schema migrations.

Add a new migration function and register it in ``MIGRATIONS`` whenever the
database schema changes.  Existing user databases will receive it once only.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable

from app.database.database import DatabaseManager, database


Migration = Callable[[sqlite3.Connection], None]


def _create_migrations_table(connection: sqlite3.Connection) -> None:
    """Create the table used to remember applied schema versions."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _migration_001_create_chat_tables(connection: sqlite3.Connection) -> None:
    """Create the initial conversation and message storage."""
    connection.execute(
        """
        CREATE TABLE conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT 'New Chat',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id)
                REFERENCES conversations(id)
                ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_conversations_updated_at
        ON conversations(updated_at DESC)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_messages_conversation_created_at
        ON messages(conversation_id, created_at ASC)
        """
    )
    connection.execute(
        """
        CREATE TRIGGER update_conversation_timestamp_after_message
        AFTER INSERT ON messages
        FOR EACH ROW
        BEGIN
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = NEW.conversation_id;
        END
        """
    )


def _migration_002_add_conversation_activity_order(connection: sqlite3.Connection) -> None:
    """Track the most recently added message without timestamp precision loss."""
    connection.execute(
        """
        ALTER TABLE conversations
        ADD COLUMN last_message_rowid INTEGER NOT NULL DEFAULT 0
        """
    )
    connection.execute(
        """
        UPDATE conversations
        SET last_message_rowid = COALESCE(
            (
                SELECT MAX(rowid)
                FROM messages
                WHERE messages.conversation_id = conversations.id
            ),
            0
        )
        """
    )
    connection.execute("DROP TRIGGER update_conversation_timestamp_after_message")
    connection.execute(
        """
        CREATE TRIGGER update_conversation_timestamp_after_message
        AFTER INSERT ON messages
        FOR EACH ROW
        BEGIN
            UPDATE conversations
            SET
                updated_at = CURRENT_TIMESTAMP,
                last_message_rowid = NEW.rowid
            WHERE id = NEW.conversation_id;
        END
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_conversations_last_message_rowid
        ON conversations(last_message_rowid DESC)
        """
    )


def _migration_003_create_attachments_table(connection: sqlite3.Connection) -> None:
    """Persist attachment metadata with the user message that sent it."""
    connection.execute(
        """
        CREATE TABLE attachments (
            id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            original_name TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            extension TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            media_type TEXT NOT NULL DEFAULT '',
            is_image INTEGER NOT NULL DEFAULT 0 CHECK (is_image IN (0, 1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        "CREATE INDEX idx_attachments_message_id ON attachments(message_id)"
    )


# The number is permanent: never renumber or edit a migration already shipped.
MIGRATIONS: dict[int, Migration] = {
    1: _migration_001_create_chat_tables,
    2: _migration_002_add_conversation_activity_order,
    3: _migration_003_create_attachments_table,
}


class DatabaseMigration:
    """Object-oriented migration entry point used by ``DatabaseService``."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def migrate(self) -> int:
        """Apply all pending migrations and return the installed version."""
        return run_migrations(self.db)


def get_current_version(db: DatabaseManager = database) -> int:
    """Return the newest migration version already applied to this database."""
    db.initialize()
    _create_migrations_table(db.get_connection())
    row = db.fetch_one("SELECT COALESCE(MAX(version), 0) AS version FROM schema_migrations")
    return int(row["version"])


def run_migrations(db: DatabaseManager = database) -> int:
    """Apply every pending migration in order and return the final version."""
    db.initialize()
    _create_migrations_table(db.get_connection())
    current_version = get_current_version(db)

    for version in sorted(MIGRATIONS):
        if version <= current_version:
            continue

        with db.transaction() as connection:
            MIGRATIONS[version](connection)
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
        current_version = version

    return current_version
