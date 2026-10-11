"""Terminal & Shell Command Execution Tool for AI Agent (Antigravity-style run_command)."""

import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import resolve_user_path, get_user_desktop_dir, get_active_workspace


MAX_OUTPUT_CHARS = 64_000

# High-risk commands that should be strictly blocked for safety
DISALLOWED_COMMANDS = {
    "format",
    "diskpart",
    "reg delete",
    "del /s /q c:\\",
    "rm -rf /",
    "mkfs",
}


class TerminalCommandTool(BaseTool):
    """Tool enabling AI Agent to execute shell / terminal commands with explicit user approval."""

    def __init__(self):
        super().__init__(
            name="run_command",
            description="Execute terminal or PowerShell commands (e.g. test suites, pip install, git commands, python scripts).",
            permission_level=PermissionLevel.REQUIRES_APPROVAL,
            version="1.0.0",
            supported_file_types=[],
            capabilities=["terminal", "run_command", "shell", "powershell", "execute_command"],
            input_schema={
                "command": "string (command line to execute)",
                "cwd": "string (optional, working directory to run command in)",
                "timeout_sec": "number (optional, default 30, max 120)",
            },
            output_schema={"stdout": "string", "stderr": "string", "exit_code": "integer"},
        )

    def execute(self, command: str = "", cwd: str = "", timeout_sec: float = 30.0, **kwargs: Any) -> ToolResult:
        cmd_str = str(command or "").strip()
        if not cmd_str:
            return ToolResult(success=False, output="", error="Command cannot be empty.")

        # Check safety blacklist
        cmd_lower = cmd_str.lower()
        for dangerous in DISALLOWED_COMMANDS:
            if dangerous in cmd_lower:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Command rejected by safety policy: contains restricted token '{dangerous}'.",
                )

        target_dir = None
        if cwd and str(cwd).strip():
            target_str = str(cwd).strip().strip("\"'")
            if target_str.lower() in ("desktop", "user desktop"):
                target_dir = get_user_desktop_dir()
            else:
                target_dir = resolve_user_path(target_str)
        else:
            workspace = get_active_workspace()
            target_dir = Path(workspace) if workspace else Path.cwd()

        target_dir = Path(target_dir).resolve(strict=False)
        if not target_dir.exists() or not target_dir.is_dir():
            target_dir = Path.cwd()

        try:
            timeout_val = max(1.0, min(float(timeout_sec), 120.0))
        except (ValueError, TypeError):
            timeout_val = 30.0

        start_time = time.perf_counter()
        try:
            # Use PowerShell on Windows for modern command execution
            process = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd_str],
                cwd=str(target_dir),
                capture_output=True,
                text=True,
                timeout=timeout_val,
                shell=False,
                encoding="utf-8",
                errors="replace",
            )
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

            stdout = process.stdout or ""
            stderr = process.stderr or ""

            if len(stdout) > MAX_OUTPUT_CHARS:
                stdout = stdout[:MAX_OUTPUT_CHARS] + "\n[Output truncated for size limit]"
            if len(stderr) > MAX_OUTPUT_CHARS:
                stderr = stderr[:MAX_OUTPUT_CHARS] + "\n[Stderr truncated for size limit]"

            combined_output = []
            if stdout:
                combined_output.append(stdout.strip())
            if stderr:
                combined_output.append(f"STDERR:\n{stderr.strip()}")
            if not stdout and not stderr:
                combined_output.append(f"[Command executed with exit code {process.returncode} and no stdout]")

            full_output = "\n".join(combined_output)
            is_success = (process.returncode == 0)

            return ToolResult(
                success=is_success,
                output=full_output,
                error=f"Command exited with code {process.returncode}" if not is_success else None,
                execution_time_ms=elapsed_ms,
                data={
                    "command": cmd_str,
                    "cwd": str(target_dir),
                    "exit_code": process.returncode,
                },
            )

        except subprocess.TimeoutExpired:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {timeout_val:.1f} seconds.",
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to execute command: {exc}",
                execution_time_ms=elapsed_ms,
            )
