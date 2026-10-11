"""Git Repository & Diff Inspection Tool for AI Agent (Claude Code style version control awareness)."""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import get_active_workspace, get_user_desktop_dir


class GitTool(BaseTool):
    """Tool enabling AI Agent to inspect git status, view diffs of edits, and inspect branch/history."""

    def __init__(self):
        super().__init__(
            name="git_tool",
            description="Inspect git version control state: 'status' (changed files), 'diff' (exact code changes), 'log' (recent commits), or 'branch'.",
            permission_level=PermissionLevel.READ_ONLY,
            version="1.0.0",
            supported_file_types=[],
            capabilities=["git", "git_tool", "git_status", "git_diff", "git_log", "version_control"],
            input_schema={
                "action": "string (optional: 'status', 'diff', 'log', 'branch' - default 'status')",
                "file_path": "string (optional, specific file path to diff)",
            },
            output_schema={"action": "string", "output": "string"},
        )

    def execute(self, action: str = "status", file_path: str = "", **kwargs: Any) -> ToolResult:
        try:
            workspace = get_active_workspace()
            target_dir = Path(workspace) if workspace else Path.cwd()

            act = str(action or "status").strip().lower()
            if act not in ("status", "diff", "log", "branch"):
                act = "status"

            # Check if directory has .git folder or is inside a worktree
            git_check = subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if git_check.returncode != 0:
                return ToolResult(
                    success=True,
                    output=f"Notice: The workspace '{target_dir.name}' is not currently a Git repository.",
                    data={"is_git": False, "action": act},
                )

            # Build command according to requested action
            if act == "status":
                cmd = ["git", "status", "--short"]
            elif act == "diff":
                cmd = ["git", "diff"]
                if file_path and str(file_path).strip():
                    cmd.append(str(file_path).strip().strip("\"'"))
            elif act == "log":
                cmd = ["git", "log", "-n", "8", "--oneline"]
            elif act == "branch":
                cmd = ["git", "branch", "--show-current"]
            else:
                cmd = ["git", "status", "--short"]

            res = subprocess.run(
                cmd,
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )

            stdout = res.stdout.strip()
            stderr = res.stderr.strip()

            if res.returncode != 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Git command failed: {stderr or stdout}",
                    data={"action": act, "exit_code": res.returncode},
                )

            if not stdout:
                if act == "status":
                    stdout = "Working tree clean (no modified or untracked files)."
                elif act == "diff":
                    stdout = "No uncommitted diffs found."
                else:
                    stdout = "(Empty git output)"

            formatted_output = f"Git {act.upper()} [{target_dir.name}]:\n{stdout}"
            return ToolResult(
                success=True,
                output=formatted_output,
                data={"is_git": True, "action": act, "output": stdout},
            )

        except FileNotFoundError:
            return ToolResult(
                success=True,
                output="Notice: 'git' is not installed or not available in the system PATH.",
                data={"is_git": False, "git_installed": False},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Git inspection error: {exc}")
