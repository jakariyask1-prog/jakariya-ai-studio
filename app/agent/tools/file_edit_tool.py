"""Targeted in-place file editing tool (Antigravity-style replace_file_content)."""

import difflib
from pathlib import Path
from typing import Dict, Any

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import (
    resolve_agent_write_path,
    get_windows_shell_folder,
    get_active_workspace,
    _is_within,
)


class FileEditTool(BaseTool):
    """Tool enabling AI Agent to perform precise surgical edits by replacing target snippets."""

    def __init__(self):
        super().__init__(
            name="edit_file",
            description="Perform surgical in-place edits in a file by finding exact target_content and replacing with replacement_content.",
            permission_level=PermissionLevel.REQUIRES_APPROVAL,
            version="1.0.0",
            supported_file_types=[".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".txt", ".csv"],
            capabilities=["edit_file", "replace_content", "patch_file", "code_refactor"],
            input_schema={
                "file_path": "string",
                "target_content": "string (exact text chunk to replace)",
                "replacement_content": "string (new text to insert in place)",
                "allow_multiple": "boolean (optional, default False)",
            },
            output_schema={"modified_path": "string", "replacements_count": "integer"},
        )

    def execute(
        self,
        file_path: str = "",
        target_content: str = "",
        replacement_content: str = "",
        allow_multiple: bool = False,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            if not file_path or not file_path.strip():
                return ToolResult(success=False, output="", error="file_path cannot be empty.")
            if not target_content:
                return ToolResult(success=False, output="", error="target_content to find cannot be empty.")

            resolved_p = resolve_agent_write_path(file_path)
            if not resolved_p.exists():
                return ToolResult(success=False, output="", error=f"File to edit does not exist: {resolved_p}")

            original_text = resolved_p.read_text(encoding="utf-8")
            clean_target = target_content.replace("\r\n", "\n")
            clean_replacement = replacement_content.replace("\r\n", "\n")

            count = original_text.count(clean_target)

            if count == 0 and "\r\n" in original_text:
                target_crlf = clean_target.replace("\n", "\r\n")
                if target_crlf in original_text:
                    clean_target = target_crlf
                    clean_replacement = clean_replacement.replace("\n", "\r\n")
                    count = original_text.count(clean_target)

            if count == 0 and clean_target.strip():
                trimmed = clean_target.strip()
                if trimmed in original_text and (original_text.count(trimmed) == 1 or allow_multiple):
                    clean_target = trimmed
                    clean_replacement = clean_replacement.strip()
                    count = original_text.count(clean_target)

            if count == 0:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"target_content was not found in {resolved_p.name}. Make sure formatting and whitespace match exactly.",
                )

            if count > 1 and not allow_multiple:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"target_content occurs {count} times in {resolved_p.name}. Provide a more unique block of context or set allow_multiple=True.",
                )

            if allow_multiple:
                new_text = original_text.replace(clean_target, clean_replacement)
                replaced_count = count
            else:
                new_text = original_text.replace(clean_target, clean_replacement, 1)
                replaced_count = 1

            # Compute unified diff line statistics (+added / -removed)
            old_lines = original_text.splitlines(keepends=True)
            new_lines = new_text.splitlines(keepends=True)
            diff = list(difflib.unified_diff(
                old_lines,
                new_lines,
                fromfile=f"a/{resolved_p.name}",
                tofile=f"b/{resolved_p.name}",
            ))
            lines_added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
            lines_removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
            diff_text = "".join(diff)

            # Calculate parent folder relative to workspace
            workspace = get_active_workspace()
            try:
                if workspace and _is_within(resolved_p, Path(workspace)):
                    rel_p = resolved_p.relative_to(Path(workspace))
                    folder_str = str(rel_p.parent).replace("\\", "/") if str(rel_p.parent) != "." else "root"
                else:
                    folder_str = resolved_p.parent.name
            except Exception:
                folder_str = resolved_p.parent.name

            diff_stat = f"+{lines_added} / -{lines_removed}"

            resolved_p.write_text(new_text, encoding="utf-8")

            # Mirror to real Windows Shell Desktop if saved in home / Desktop
            shell_desktop = get_windows_shell_folder("Desktop")
            if (
                shell_desktop
                and shell_desktop.exists()
                and _is_within(resolved_p, Path.home() / "Desktop")
                and not _is_within(resolved_p, shell_desktop)
            ):
                try:
                    rel = resolved_p.relative_to(Path.home() / "Desktop")
                    mirror_target = shell_desktop / rel
                    if mirror_target.exists():
                        mirror_target.write_text(new_text, encoding="utf-8")
                except Exception:
                    pass

            output_msg = (
                f"Successfully edited {resolved_p.name} in '{folder_str}' "
                f"({diff_stat} lines): replaced {replaced_count} occurrence(s)."
            )

            return ToolResult(
                success=True,
                output=output_msg,
                data={
                    "modified_path": str(resolved_p.resolve()),
                    "saved_path": str(resolved_p.resolve()),
                    "file_name": resolved_p.name,
                    "folder": folder_str,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "diff_stat": diff_stat,
                    "replacements_count": replaced_count,
                    "action": "modified",
                    "diff_text": diff_text,
                },
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Error editing file: {exc}")
