"""Recursive Code & Text Search (Grep) Tool across project workspaces for AI Agent."""

import fnmatch
import os
import re
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

TEXT_EXTENSIONS = {
    ".py", ".pyw", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".php", ".phtml", ".vue", ".svelte", ".astro",
    ".json", ".jsonc", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env",
    ".sql", ".prisma", ".graphql", ".gql",
    ".md", ".txt", ".csv", ".tsv",
    ".sh", ".bash", ".bat", ".cmd", ".ps1",
    ".c", ".cpp", ".cc", ".h", ".hpp", ".cs", ".rs", ".go", ".java", ".rb",
}


class FileSearchTool(BaseTool):
    """Tool enabling AI Agent to perform multi-file code and text search (Grep) across a workspace."""

    def __init__(self):
        super().__init__(
            name="search_files",
            description="Search for keywords, functions, classes, or patterns across all files in a folder (Grep).",
            permission_level=PermissionLevel.READ_ONLY,
            version="1.0.0",
            supported_file_types=[],
            capabilities=["search_files", "grep", "code_search", "find_in_files"],
            input_schema={
                "query": "string (keyword or regex to search for)",
                "folder_path": "string (optional, defaults to workspace/project folder)",
                "file_pattern": "string (optional, e.g. '*.py', '*.json', default all text/code files)",
                "max_results": "integer (optional, default 30)",
            },
            output_schema={"matches": "list", "total_matches": "integer"},
        )

    def execute(
        self,
        query: str = "",
        folder_path: str = "",
        file_pattern: str = "",
        max_results: int = 30,
        **kwargs: Any,
    ) -> ToolResult:
        clean_query = str(query or "").strip().strip("\"'")
        if not clean_query:
            return ToolResult(success=False, output="", error="Search query cannot be empty.")

        target_str = str(folder_path or "").strip().strip("\"'")
        if not target_str or target_str in (".", "workspace", "cwd", "current"):
            workspace = get_active_workspace()
            target_path = Path(workspace) if workspace else get_user_desktop_dir()
        elif target_str.lower() in ("desktop", "user desktop"):
            target_path = get_user_desktop_dir()
        else:
            target_path = resolve_user_path(target_str)

        target_path = target_path.resolve(strict=False)

        if not target_path.exists() or not target_path.is_dir():
            return ToolResult(success=False, output="", error=f"Search folder not found: {target_path}")

        try:
            limit = max(1, min(int(max_results), 100))
        except (ValueError, TypeError):
            limit = 30

        try:
            # Case-insensitive regex search
            pattern = re.compile(re.escape(clean_query), re.IGNORECASE)
        except Exception:
            pattern = re.compile(clean_query, re.IGNORECASE)

        pattern_filter = str(file_pattern or "").strip()

        matched_files_count = 0
        total_matches = 0
        formatted_results: List[str] = [f"🔍 Search results for '{clean_query}' in: {target_path}"]

        for root, dirs, files in os.walk(target_path):
            # Prune ignored directories in-place
            dirs[:] = [
                d for d in dirs
                if d.lower() not in IGNORE_DIR_NAMES and not d.startswith(".")
            ]

            for file_name in files:
                if pattern_filter and not fnmatch.fnmatch(file_name, pattern_filter):
                    continue

                ext = Path(file_name).suffix.lower()
                if not pattern_filter and ext and ext not in TEXT_EXTENSIONS:
                    continue

                full_file_path = Path(root) / file_name
                try:
                    # Skip files larger than 2MB for fast searching
                    if full_file_path.stat().st_size > 2 * 1024 * 1024:
                        continue

                    content = full_file_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

                file_matches: List[str] = []
                for line_num, line in enumerate(content.splitlines(), start=1):
                    if pattern.search(line):
                        total_matches += 1
                        snippet = line.strip()
                        if len(snippet) > 120:
                            snippet = snippet[:117] + "..."
                        file_matches.append(f"  Line {line_num}: {snippet}")

                        if total_matches >= limit:
                            break

                if file_matches:
                    matched_files_count += 1
                    try:
                        rel_display = full_file_path.relative_to(target_path)
                    except ValueError:
                        rel_display = full_file_path
                    formatted_results.append(f"\n📄 {rel_display}:")
                    formatted_results.extend(file_matches)

                if total_matches >= limit:
                    break

            if total_matches >= limit:
                formatted_results.append(f"\n[Search capped at {limit} maximum matches. More results may exist.]")
                break

        if total_matches == 0:
            formatted_results.append(f"\nNo occurrences found for '{clean_query}'.")

        return ToolResult(
            success=True,
            output="\n".join(formatted_results),
            data={
                "query": clean_query,
                "folder": str(target_path),
                "total_matches": total_matches,
                "matched_files": matched_files_count,
            },
        )
