"""Application-level database startup and shutdown service."""

from __future__ import annotations

from app.database.database import DatabaseManager, database
from app.database.migrations import DatabaseMigration


class DatabaseService:
    """Own the database manager and apply migrations during application startup."""

    def __init__(self, db: DatabaseManager | None = None) -> None:
        # Reuse the application-wide manager used by repositories.
        self.db = db or database
        self.migration = DatabaseMigration(self.db)

    def initialize(self) -> int:
        """Open the database and install every pending schema migration."""
        self.db.connect()
        return self.migration.migrate()

    def close(self) -> None:
        """Close the current thread's database connection."""
        self.db.close()
