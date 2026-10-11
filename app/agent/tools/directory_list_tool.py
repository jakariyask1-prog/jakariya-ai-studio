"""Directory Listing & Project Tree Exploration Tool for AI Agent."""

import os
from pathlib import Path
from typing import Dict, Any, List

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import resolve_user_path, get_user_desktop_dir, get_active_workspace


IGNORE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
    "$recycle.bin",
    "system volume information",
}


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class DirectoryListTool(BaseTool):
    """Tool enabling AI Agent to inspect directory tree structures and discover files."""

    def __init__(self):
        super().__init__(
            name="list_directory",
            description="Explore and list all files and subfolders within a directory in a clear tree structure.",
            permission_level=PermissionLevel.READ_ONLY,
            version="1.0.0",
            supported_file_types=[],
            capabilities=["list_directory", "file_tree", "codebase_exploration", "browse_folder"],
            input_schema={
                "folder_path": "string (optional, defaults to current project/workspace or Desktop)",
                "max_depth": "integer (optional, default 3, max 6)",
            },
            output_schema={"tree": "string", "file_count": "integer", "dir_count": "integer"},
        )

    def execute(self, folder_path: str = "", max_depth: int = 3, **kwargs: Any) -> ToolResult:
        try:
            target_str = str(folder_path or "").strip().strip("\"'")
            if not target_str or target_str in (".", "workspace", "cwd", "current"):
                target_path = get_active_workspace()
            elif target_str.lower() in ("desktop", "user desktop"):
                target_path = get_user_desktop_dir()
            else:
                target_path = resolve_user_path(target_str)

            target_path = target_path.resolve(strict=False)

            if not target_path.exists():
                return ToolResult(success=False, output="", error=f"Directory not found: {target_path}")

            if not target_path.is_dir():
                return ToolResult(success=False, output="", error=f"Path is a file, not a directory: {target_path}")

            try:
                depth_limit = max(1, min(int(max_depth), 6))
            except (ValueError, TypeError):
                depth_limit = 3

            lines: List[str] = [f"📁 Directory: {target_path}"]
            file_count = 0
            dir_count = 0

            def build_tree(current_dir: Path, prefix: str = "", current_depth: int = 1) -> None:
                nonlocal file_count, dir_count
                if current_depth > depth_limit:
                    return

                try:
                    entries = sorted(
                        list(current_dir.iterdir()),
                        key=lambda e: (not e.is_dir(), e.name.lower())
                    )
                except PermissionError:
                    lines.append(f"{prefix}└── [Permission Denied]")
                    return

                # Filter ignored directories and hidden files
                filtered = [
                    e for e in entries
                    if e.name.lower() not in IGNORE_DIR_NAMES
                    and not (e.name.startswith(".") and e.is_dir())
                ]

                total_items = len(filtered)
                for index, entry in enumerate(filtered):
                    is_last = (index == total_items - 1)
                    connector = "└── " if is_last else "├── "
                    sub_prefix = "    " if is_last else "│   "

                    if entry.is_dir():
                        dir_count += 1
                        lines.append(f"{prefix}{connector}📁 {entry.name}/")
                        build_tree(entry, prefix + sub_prefix, current_depth + 1)
                    else:
                        file_count += 1
                        try:
                            size_str = _format_size(entry.stat().st_size)
                        except OSError:
                            size_str = "unknown"
                        lines.append(f"{prefix}{connector}📄 {entry.name} ({size_str})")

            build_tree(target_path)
            lines.append(f"\nSummary: {file_count} files, {dir_count} directories (depth limit: {depth_limit})")

            output_text = "\n".join(lines)
            return ToolResult(
                success=True,
                output=output_text,
                data={
                    "folder": str(target_path),
                    "file_count": file_count,
                    "dir_count": dir_count,
                },
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Error listing directory: {exc}")
