"""Cancellation and interruption tokens for the voice pipeline."""

from __future__ import annotations

import threading


class InterruptionToken:
    """Thread-safe flag used to signal cancellation to pipeline tasks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_cancelled = False

    @property
    def is_cancelled(self) -> bool:
        """Return True if cancellation has been requested."""
        with self._lock:
            return self._is_cancelled

    def cancel(self) -> None:
        """Request cancellation of the active operation."""
        with self._lock:
            self._is_cancelled = True
