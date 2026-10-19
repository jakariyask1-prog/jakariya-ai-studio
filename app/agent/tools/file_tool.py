import os
from pathlib import Path
from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel


MAX_READ_BYTES = 5 * 1024 * 1024
MAX_EXTRACTED_CHARS = 1_000_000
SUPPORTED_READ_SUFFIXES = {
    # Text, Markdown, Data & Documents
    ".txt", ".md", ".markdown", ".csv", ".tsv", ".docx", ".pdf",
    # Python
    ".py", ".pyw", ".ipynb",
    # Web & Styles
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    # JavaScript, TypeScript, React & Next.js
    ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    # Modern Web Frameworks
    ".vue", ".svelte", ".astro",
    # PHP & Backend
    ".php", ".phtml", ".php3", ".php4", ".php5", ".phps",
    # Systems & Compiled Languages
    ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".cs", ".java", ".go", ".rs", ".rb", ".swift", ".kt",
    # Configuration, Environment & Data
    ".json", ".jsonc", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".properties",
    # Database & Query
    ".sql", ".prisma", ".graphql", ".gql",
    # Shell & Scripting
    ".sh", ".bash", ".bat", ".cmd", ".ps1",
}


def _is_within(path: Path, root: Path) -> bool:
    """Return whether *path* is contained by *root* after resolving links."""
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except (ValueError, RuntimeError):
        return False


def get_windows_shell_folder(folder_id: str) -> Path | None:
    """Retrieve actual Windows Shell folder location (handling OneDrive and registry redirection)."""
    import sys
    if sys.platform != "win32":
        return None
    try:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            val, _ = winreg.QueryValueEx(key, folder_id)
            expanded = os.path.expandvars(val)
            p = Path(expanded).resolve(strict=False)
            if p.exists():
                return p
    except Exception:
        pass
    return None


def get_user_desktop_dir() -> Path:
    """Return the active user Desktop path (preferring real Windows Shell / OneDrive Desktop)."""
    shell_desktop = get_windows_shell_folder("Desktop")
    if shell_desktop and shell_desktop.exists():
        return shell_desktop
    return Path.home() / "Desktop"


def get_user_documents_dir() -> Path:
    """Return the active user Documents path (preferring real Windows Shell / OneDrive Documents)."""
    shell_docs = get_windows_shell_folder("Personal")
    if shell_docs and shell_docs.exists():
        return shell_docs
    return Path.home() / "Documents"


def get_user_downloads_dir() -> Path:
    """Return the active user Downloads path."""
    shell_dl = get_windows_shell_folder("{374DE290-123F-4565-9164-39C4925E467B}")
    if shell_dl and shell_dl.exists():
        return shell_dl
    return Path.home() / "Downloads"


_CURRENT_WORKSPACE_OVERRIDE: Path | None = None


def set_active_workspace(folder_path: str | Path | None) -> None:
    """Set an active project workspace directory (e.g. from UI folder picker or drag-drop)."""
    global _CURRENT_WORKSPACE_OVERRIDE
    if folder_path:
        p = Path(folder_path).resolve(strict=False)
        if p.exists() and p.is_dir():
            _CURRENT_WORKSPACE_OVERRIDE = p
            return
    _CURRENT_WORKSPACE_OVERRIDE = None


def get_active_workspace() -> Path:
    """Return the currently selected project workspace or default to Path.cwd()."""
    global _CURRENT_WORKSPACE_OVERRIDE
    if _CURRENT_WORKSPACE_OVERRIDE is not None and _CURRENT_WORKSPACE_OVERRIDE.exists():
        return _CURRENT_WORKSPACE_OVERRIDE
    return Path.cwd().resolve()


def get_allowed_agent_write_roots() -> tuple[Path, ...]:
    """Return all directories where the AI Agent is allowed to create or modify user documents."""
    home = Path.home().resolve(strict=False)
    roots: list[Path] = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Documents" / "Jakariya AI Studio" / "Agent Workspace",
        Path.cwd().resolve(strict=False),
        get_active_workspace(),
    ]

    # Add Windows Shell Folders (e.g. OneDrive Desktop, Documents, Downloads)
    for shell_id in ("Desktop", "Personal", "{374DE290-123F-4565-9164-39C4925E467B}"):
        folder = get_windows_shell_folder(shell_id)
        if folder and folder not in roots:
            roots.append(folder)

    # Add OneDrive environment paths
    for env_var in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        env_val = os.getenv(env_var)
        if env_val:
            one_p = Path(env_val).resolve(strict=False)
            if one_p.exists() and one_p not in roots:
                roots.append(one_p)

    return tuple(roots)


def resolve_user_path(file_path: str) -> Path:
    """Resolve file paths to actual Windows user directories (Desktop, Documents, Downloads).

    Prevents relative paths from saving into the project root folder and fixes generic user placeholders.
    """
    if not isinstance(file_path, str):
        file_path = str(file_path)

    clean_path = file_path.strip().strip("\"'")

    # Extract clean file path if raw JSON artifact was passed in file_path
    if "{" in clean_path and "}" in clean_path:
        import re
        match = re.search(r'"(?:file_path|path|filename)"\s*:\s*"([^"]+)"', clean_path)
        if match:
            clean_path = match.group(1)
        else:
            clean_path = re.sub(r'[{}\[\]"]', '', clean_path).strip()

    if not clean_path:
        raise ValueError("File path cannot be empty.")

    expanded = os.path.expandvars(os.path.expanduser(clean_path))
    p = Path(expanded)
    home = Path.home()

    # Redirect generic Windows user placeholders (e.g. C:\Users\user) to real logged in user's profile
    p_str = str(p)
    import re
    user_match = re.match(r"^[a-zA-Z]:[/\\][uU]sers[/\\]([^/\\]+)(?:[/\\](.*))?$", p_str)
    if user_match:
        target_user = user_match.group(1)
        rest_of_path = user_match.group(2) or ""
        user_folder = Path(p_str[:user_match.end(1)])
        if target_user.lower() in ("user", "username", "admin", "yourname", "your_username") or not user_folder.exists():
            if rest_of_path:
                return resolve_user_path(rest_of_path)
            return home / "Desktop"

    if p.is_absolute():
        return p

    # If the relative path exists in the active workspace or CWD, prioritize it!
    workspace = get_active_workspace()
    if workspace and (workspace / p).exists():
        return (workspace / p).resolve()
    if (Path.cwd() / p).exists():
        return (Path.cwd() / p).resolve()

    parts = p.parts
    first_part = parts[0].lower() if parts else ""

    if first_part == "desktop":
        target_dir = home / "Desktop"
        rel_parts = parts[1:]
        return target_dir.joinpath(*rel_parts) if rel_parts else target_dir
    elif first_part in ("documents", "doc", "docs"):
        target_dir = home / "Documents"
        rel_parts = parts[1:]
        return target_dir.joinpath(*rel_parts) if rel_parts else target_dir
    elif first_part in ("downloads", "download"):
        target_dir = home / "Downloads"
        rel_parts = parts[1:]
        return target_dir.joinpath(*rel_parts) if rel_parts else target_dir
    else:
        # When an explicit workspace override is active, default new relative files to it
        if _CURRENT_WORKSPACE_OVERRIDE is not None:
            return _CURRENT_WORKSPACE_OVERRIDE / p
        # Single filenames or unspecified relative paths default to user's Desktop
        return home / "Desktop" / p


def resolve_agent_write_path(file_path: str) -> Path:
    """Resolve a destination that an agent is allowed to create or overwrite.

    Agent output must stay in a user-facing export area.  This blocks model
    supplied paths such as application folders, other user profiles, and
    system directories while retaining the existing Desktop/Documents/
    Downloads and Workspace workflow.
    """
    candidate = resolve_user_path(file_path).resolve(strict=False)
    resolved_roots = tuple(root.resolve(strict=False) for root in get_allowed_agent_write_roots())

    if not any(_is_within(candidate, root) for root in resolved_roots):
        allowed = ", ".join(str(root) for root in resolved_roots[:3])
        raise ValueError(
            "Agent file creation is limited to Desktop, Documents, or Downloads. "
            f"Requested path is outside the allowed folders: {candidate}. Allowed roots: {allowed}."
        )
    return candidate



class FileReadTool(BaseTool):
    """Tool enabling AI Agent to read text files."""

    def __init__(self):
        super().__init__(
            name="read_file",
            description="Read contents of a local file with optional line range slicing.",
            permission_level=PermissionLevel.REQUIRES_APPROVAL,
            version="1.0.0",
            supported_file_types=[
                ".txt", ".md", ".py", ".json", ".csv", ".html", ".css", ".scss",
                ".js", ".jsx", ".ts", ".tsx", ".php", ".vue", ".svelte",
                ".c", ".cpp", ".cs", ".java", ".go", ".rs", ".sql", ".sh", ".docx", ".pdf",
            ],
            capabilities=["read_file", "file_io", "text_extraction", "line_slice"],
            input_schema={
                "file_path": "string",
                "start_line": "integer (optional, 1-indexed start line)",
                "end_line": "integer (optional, 1-indexed end line)",
                "line_numbers": "boolean (optional, default False)",
            },
            output_schema={"content": "string"},
        )

    def execute(
        self,
        file_path: str = "",
        start_line: int | None = None,
        end_line: int | None = None,
        line_numbers: bool = False,
        **kwargs,
    ) -> ToolResult:
        try:
            clean_path = (file_path or "").strip().strip("\"'")
            if not clean_path:
                return ToolResult(success=False, output="", error="No file path provided.")

            candidate = resolve_user_path(clean_path)
            resolved_p = None

            # 1. Check primary candidate path
            if candidate.exists() and candidate.is_file():
                resolved_p = candidate.resolve(strict=True)

            # 2. If not found, search alternative candidate directories (real Shell Desktop, CWD, Documents, Downloads)
            if resolved_p is None:
                p_obj = Path(clean_path)
                alt_dirs = [
                    get_active_workspace(),
                    Path.cwd(),
                    get_windows_shell_folder("Desktop"),
                    get_windows_shell_folder("Personal"),
                    get_windows_shell_folder("{374DE290-123F-4565-9164-39C4925E467B}"),
                    Path.home() / "Desktop",
                    Path.home() / "Documents",
                    Path.home() / "Downloads",
                ]
                for d in alt_dirs:
                    if not d or not d.exists():
                        continue
                    # Check direct join
                    check_p = d / p_obj
                    if check_p.is_file():
                        resolved_p = check_p.resolve(strict=True)
                        break
                    # If p_obj has parts like ("Desktop", "file.txt"), check stripped parts
                    if len(p_obj.parts) > 1 and p_obj.parts[0].lower() in ("desktop", "documents", "downloads"):
                        check_p2 = d.joinpath(*p_obj.parts[1:])
                        if check_p2.is_file():
                            resolved_p = check_p2.resolve(strict=True)
                            break

            # 3. Fallback to candidate for standard error reporting
            if resolved_p is None:
                resolved_p = candidate.resolve(strict=False)

            if not resolved_p.is_file():
                return ToolResult(success=False, output="", error=f"File not found: {resolved_p}")

            suffix = resolved_p.suffix.lower()
            if suffix not in SUPPORTED_READ_SUFFIXES:
                return ToolResult(success=False, output="", error=f"Unsupported file type: {suffix or '[no extension]'}")
            if resolved_p.stat().st_size > MAX_READ_BYTES:
                return ToolResult(success=False, output="", error=f"File is larger than the {MAX_READ_BYTES // (1024 * 1024)} MB safety limit.")

            if suffix == ".pdf":
                from pypdf import PdfReader
                content = "\n".join(page.extract_text() or "" for page in PdfReader(str(resolved_p)).pages)
            elif suffix == ".docx":
                from app.uploads.business_logic.file_parser import _extract_docx_text
                content = _extract_docx_text(resolved_p)
            else:
                content = resolved_p.read_text(encoding="utf-8", errors="replace")

            if suffix not in (".pdf", ".docx"):
                lines = content.splitlines()
                total_lines = len(lines)

                s_line = None
                e_line = None
                if start_line is not None:
                    try:
                        s_line = max(1, int(start_line))
                    except (ValueError, TypeError):
                        s_line = 1
                if end_line is not None:
                    try:
                        e_line = min(total_lines, int(end_line))
                    except (ValueError, TypeError):
                        e_line = total_lines

                if s_line is not None or e_line is not None or line_numbers:
                    actual_start = s_line if s_line is not None else 1
                    actual_end = e_line if e_line is not None else total_lines
                    if actual_start <= actual_end:
                        selected = lines[actual_start - 1 : actual_end]
                        formatted = [f"{actual_start + idx}: {line}" for idx, line in enumerate(selected)]
                        header = f"--- {resolved_p.name} (Lines {actual_start}-{actual_end} of {total_lines}) ---\n"
                        content = header + "\n".join(formatted)
                    else:
                        content = f"--- {resolved_p.name} (Empty range: {actual_start} > {actual_end}) ---"

            if len(content) > MAX_EXTRACTED_CHARS:
                content = content[:MAX_EXTRACTED_CHARS] + "\n[Content truncated for safety.]"
            return ToolResult(success=True, output=content)
        except Exception as exc:
            return ToolResult(success=False, output="", error=str(exc))


class FileWriteTool(BaseTool):
    """Tool enabling AI Agent to create or overwrite text files."""

    def __init__(self):
        super().__init__(
            name="write_file",
            description="Write content to a local text file.",
            permission_level=PermissionLevel.REQUIRES_APPROVAL,
            version="1.0.0",
            supported_file_types=[
                ".txt", ".md", ".py", ".json", ".csv", ".html", ".css", ".scss",
                ".js", ".jsx", ".ts", ".tsx", ".php", ".vue", ".svelte",
                ".c", ".cpp", ".cs", ".java", ".go", ".rs", ".sql", ".sh",
            ],
            capabilities=["write_file", "file_io", "save_document"],
            input_schema={"file_path": "string", "content": "string"},
            output_schema={"message": "string"},
        )

    def execute(self, file_path: str = "", content: str = "", **kwargs) -> ToolResult:
        try:
            resolved_p = resolve_agent_write_path(file_path)

            existed = resolved_p.exists() and resolved_p.is_file()
            old_lines = resolved_p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) if existed else []
            new_lines = content.splitlines(keepends=True)

            import difflib
            if existed:
                diff = list(difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{resolved_p.name}",
                    tofile=f"b/{resolved_p.name}",
                ))
                lines_added = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
                lines_removed = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))
                diff_text = "".join(diff)
                if not diff_text:
                    diff_text = f"--- a/{resolved_p.name}\n+++ b/{resolved_p.name}\n# No changes detected (content is identical)."
                action = "overwritten"
            else:
                diff = list(difflib.unified_diff(
                    [],
                    new_lines,
                    fromfile="/dev/null",
                    tofile=f"b/{resolved_p.name}",
                ))
                lines_added = len(new_lines)
                lines_removed = 0
                diff_text = "".join(diff)
                action = "created"

            resolved_p.parent.mkdir(parents=True, exist_ok=True)
            resolved_p.write_text(content, encoding="utf-8")

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

            diff_stat = f"+{lines_added} / -{lines_removed}" if existed else f"+{lines_added}"

            # If writing to home / Desktop and a distinct Windows Shell Desktop exists,
            # also mirror the file to the real Windows Shell Desktop so the user can immediately see it!
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
                    mirror_target.parent.mkdir(parents=True, exist_ok=True)
                    mirror_target.write_text(content, encoding="utf-8")
                except Exception:
                    pass

            output_msg = (
                f"Successfully wrote {resolved_p.name} in '{folder_str}' "
                f"({diff_stat} lines, {len(content)} chars)."
            )

            return ToolResult(
                success=True,
                output=output_msg,
                data={
                    "saved_path": str(resolved_p.resolve()),
                    "modified_path": str(resolved_p.resolve()),
                    "file_name": resolved_p.name,
                    "folder": folder_str,
                    "lines_added": lines_added,
                    "lines_removed": lines_removed,
                    "diff_stat": diff_stat,
                    "action": action,
                    "diff_text": diff_text,
                },
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Permission or path error writing file: {exc}")
