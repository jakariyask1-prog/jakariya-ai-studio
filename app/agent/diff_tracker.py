"""Central Diff & Code Change Tracker for Jakariya AI Studio (Antigravity-Style)."""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class DiffRecord:
    """Record representing code change metrics and unified diff for one file."""
    file_path: str
    file_name: str
    folder: str
    lines_added: int = 0
    lines_removed: int = 0
    action: str = "modified"  # modified, created, overwritten
    diff_text: str = ""
    timestamp: float = 0.0


class DiffTracker:
    """Singleton tracker maintaining change history for agent runs."""

    _instance: Optional[DiffTracker] = None

    def __init__(self):
        self._sessions: Dict[str, Dict[str, DiffRecord]] = {"latest": {}}

    @classmethod
    def instance(cls) -> DiffTracker:
        if cls._instance is None:
            cls._instance = DiffTracker()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        if cls._instance:
            cls._instance._sessions = {"latest": {}}

    def record_change(
        self,
        file_path: str,
        file_name: str,
        folder: str,
        lines_added: int = 0,
        lines_removed: int = 0,
        action: str = "modified",
        diff_text: str = "",
        session_id: str = "latest",
    ) -> None:
        """Record or aggregate change statistics for a file."""
        if session_id not in self._sessions:
            self._sessions[session_id] = {}

        import time
        norm_path = str(Path(file_path).resolve()) if file_path else file_name

        if norm_path in self._sessions[session_id]:
            rec = self._sessions[session_id][norm_path]
            rec.lines_added += lines_added
            rec.lines_removed += lines_removed
            rec.action = action
            if diff_text:
                rec.diff_text = diff_text
            rec.timestamp = time.time()
        else:
            self._sessions[session_id][norm_path] = DiffRecord(
                file_path=norm_path,
                file_name=file_name or Path(norm_path).name,
                folder=folder or Path(norm_path).parent.name,
                lines_added=lines_added,
                lines_removed=lines_removed,
                action=action,
                diff_text=diff_text,
                timestamp=time.time(),
            )

    def get_changes(self, session_id: str = "latest") -> List[DiffRecord]:
        """Return list of recorded changes for the session."""
        session_dict = self._sessions.get(session_id, {})
        return list(session_dict.values())

    def clear(self, session_id: str = "latest") -> None:
        """Clear recorded changes for a session."""
        if session_id in self._sessions:
            self._sessions[session_id].clear()
