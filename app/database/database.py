"""SQLite database manager.

All database access in the application should go through this module.
Repository classes may contain SQL, but UI classes and chat business logic
must not create SQLite connections directly.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class DatabaseManager:
    """Provide one configured SQLite connection per application thread."""

    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path or self._default_database_path())
        self._connections = threading.local()
        self._transaction_lock = threading.RLock()

    @staticmethod
    def _default_database_path() -> Path:
        """Use a location that remains writable after a PyInstaller build."""
        local_app_data = os.getenv("LOCALAPPDATA")
        base_path = Path(local_app_data) if local_app_data else Path.home() / ".jakariya_ai_studio"
        return base_path / "Jakariya AI Studio" / "jakariya_ai_studio.db"

    def initialize(self) -> None:
        """Create the database directory and configure this thread's connection."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.get_connection()

    def connect(self) -> sqlite3.Connection:
        """Initialize storage and return the current thread's connection."""
        self.initialize()
        return self.get_connection()

    def get_connection(self) -> sqlite3.Connection:
        """Get the current thread's configured SQLite connection."""
        connection = getattr(self._connections, "connection", None)
        if connection is not None:
            return connection

        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            isolation_level=None,  # Auto-commit, unless transaction() is used.
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")

        self._connections.connection = connection
        return connection

    def execute(self, query: str, parameters: Sequence[Any] = ()) -> sqlite3.Cursor:
        """Run one INSERT, UPDATE, DELETE, or DDL statement."""
        return self.get_connection().execute(query, parameters)

    def execute_many(
        self,
        query: str,
        parameter_sets: Sequence[Sequence[Any]],
    ) -> sqlite3.Cursor:
        """Run one statement against several parameter sets."""
        return self.get_connection().executemany(query, parameter_sets)

    def fetch_one(
        self,
        query: str,
        parameters: Sequence[Any] = (),
    ) -> sqlite3.Row | None:
        """Return the first matching row, or ``None``."""
        return self.get_connection().execute(query, parameters).fetchone()

    def fetch_all(
        self,
        query: str,
        parameters: Sequence[Any] = (),
    ) -> list[sqlite3.Row]:
        """Return every matching row."""
        return self.get_connection().execute(query, parameters).fetchall()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Run related operations atomically and rollback if any operation fails."""
        with self._transaction_lock:
            connection = self.get_connection()
            try:
                connection.execute("BEGIN")
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def close(self) -> None:
        """Close the database connection for the current thread."""
        connection = getattr(self._connections, "connection", None)
        if connection is not None:
            connection.close()
            self._connections.connection = None


# Import this shared manager from repositories and migrations.
database = DatabaseManager()
