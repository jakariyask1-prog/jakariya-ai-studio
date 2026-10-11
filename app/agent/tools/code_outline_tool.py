"""Code Outline & Symbol Discovery Tool for AI Agent (Cursor-style AST navigation)."""

import ast
import re
from pathlib import Path
from typing import Any, Dict, List

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import resolve_user_path, get_active_workspace, get_user_desktop_dir


class CodeOutlineTool(BaseTool):
    """Tool enabling AI Agent to inspect classes, methods, functions, and symbols of any code file."""

    def __init__(self):
        super().__init__(
            name="code_outline",
            description="Extract classes, methods, functions, and symbols with line numbers from a code file without reading the entire file (Cursor/IDE style outline).",
            permission_level=PermissionLevel.READ_ONLY,
            version="1.0.0",
            supported_file_types=[".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".go", ".rs", ".php", ".rb", ".html"],
            capabilities=["code_outline", "symbol_search", "inspect_symbols", "ast_analysis"],
            input_schema={
                "file_path": "string (path to the code file to outline)",
            },
            output_schema={"outline": "string", "symbols_count": "integer"},
        )

    def execute(self, file_path: str = "", **kwargs: Any) -> ToolResult:
        try:
            clean_path = str(file_path or "").strip().strip("\"'")
            if not clean_path:
                return ToolResult(success=False, output="", error="file_path cannot be empty.")

            candidate = resolve_user_path(clean_path)
            target_p = None
            if candidate.exists() and candidate.is_file():
                target_p = candidate.resolve()
            else:
                workspace = get_active_workspace()
                check = (workspace / clean_path).resolve() if workspace else None
                if check and check.exists() and check.is_file():
                    target_p = check
                else:
                    desktop = get_user_desktop_dir()
                    check2 = (desktop / clean_path).resolve()
                    if check2.exists() and check2.is_file():
                        target_p = check2

            if not target_p or not target_p.is_file():
                return ToolResult(success=False, output="", error=f"File not found: {clean_path}")

            code_text = target_p.read_text(encoding="utf-8", errors="replace")
            total_lines = len(code_text.splitlines())
            suffix = target_p.suffix.lower()

            if suffix == ".py":
                outline_str, count = self._outline_python(code_text, target_p.name, total_lines)
            elif suffix in (".html", ".htm"):
                outline_str, count = self._outline_html(code_text, target_p.name, total_lines)
            else:
                outline_str, count = self._outline_generic(code_text, target_p.name, total_lines)

            return ToolResult(
                success=True,
                output=outline_str,
                data={"file": str(target_p), "symbols_count": count, "total_lines": total_lines},
            )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Failed to generate code outline: {exc}")

    def _outline_python(self, code_text: str, filename: str, total_lines: int) -> tuple[str, int]:
        try:
            tree = ast.parse(code_text, filename=filename)
        except SyntaxError as e:
            return (
                f"File: {filename} ({total_lines} lines)\n⚠️ SyntaxError during AST parse on line {e.lineno}: {e.msg}\nFalling back to text scan.\n",
                0,
            )

        lines: list[str] = [f"File: {filename} ({total_lines} lines, Python AST Outline)\n"]
        symbol_count = 0

        # Collect top-level imports
        imports: list[str] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                names = ", ".join(alias.name for alias in node.names)
                imports.append(f"  Line {node.lineno}: import {names}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = ", ".join(alias.name for alias in node.names)
                imports.append(f"  Line {node.lineno}: from {module} import {names}")

        if imports:
            lines.append("📦 Imports:")
            lines.extend(imports[:15])
            if len(imports) > 15:
                lines.append(f"  ... and {len(imports) - 15} more imports")
            lines.append("")

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                symbol_count += 1
                end_lineno = getattr(node, "end_lineno", node.lineno)
                bases = ", ".join(ast.unparse(b) for b in node.bases) if node.bases else ""
                base_str = f"({bases})" if bases else ""
                lines.append(f"🏛️ Class: {node.name}{base_str} (Lines {node.lineno}-{end_lineno})")

                doc = ast.get_docstring(node)
                if doc:
                    first_doc = doc.strip().split("\n")[0]
                    lines.append(f"   Doc: \"{first_doc[:80]}\"")

                methods: list[str] = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        symbol_count += 1
                        prefix = "async def" if isinstance(item, ast.AsyncFunctionDef) else "def"
                        args_list = [a.arg for a in item.args.args]
                        ret_annot = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                        methods.append(f"   ├── Line {item.lineno}: {prefix} {item.name}({', '.join(args_list)}){ret_annot}")
                if methods:
                    lines.extend(methods)
                lines.append("")

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbol_count += 1
                prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                args_list = [a.arg for a in node.args.args]
                ret_annot = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                end_lineno = getattr(node, "end_lineno", node.lineno)
                lines.append(f"⚡ Function: {prefix} {node.name}({', '.join(args_list)}){ret_annot} (Lines {node.lineno}-{end_lineno})")
                doc = ast.get_docstring(node)
                if doc:
                    first_doc = doc.strip().split("\n")[0]
                    lines.append(f"   Doc: \"{first_doc[:80]}\"")

        return "\n".join(lines).strip(), symbol_count

    def _outline_generic(self, code_text: str, filename: str, total_lines: int) -> tuple[str, int]:
        lines: list[str] = [f"File: {filename} ({total_lines} lines, Symbol Outline)\n"]
        symbol_count = 0

        # Patterns for JS/TS/C/Java functions and classes
        patterns = [
            ("🏛️ Class / Struct / Interface", re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:class|interface|struct|type|enum)\s+([A-Za-z0-9_$]+)", re.MULTILINE)),
            ("⚡ Function / Method", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function\s+([A-Za-z0-9_$]+)|(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", re.MULTILINE)),
            ("⚡ Method / Def", re.compile(r"^\s*(?:public|private|protected|static|fn|func|def)\s+([A-Za-z0-9_$]+)\s*\(", re.MULTILINE)),
        ]

        text_lines = code_text.splitlines()
        found_symbols: list[str] = []

        for lineno, line in enumerate(text_lines, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("//", "/*", "*", "#")):
                continue

            for category, regex in patterns:
                m = regex.search(line)
                if m:
                    name = next((g for g in m.groups() if g), None)
                    if name:
                        symbol_count += 1
                        found_symbols.append(f"  Line {lineno}: {category} -> {name}")
                        break

        if found_symbols:
            lines.extend(found_symbols[:50])
            if len(found_symbols) > 50:
                lines.append(f"  ... and {len(found_symbols) - 50} more symbols")
        else:
            lines.append("  (No top-level class or function symbols detected via regex)")

        return "\n".join(lines).strip(), symbol_count

    def _outline_html(self, code_text: str, filename: str, total_lines: int) -> tuple[str, int]:
        lines: list[str] = [f"File: {filename} ({total_lines} lines, HTML Document Outline)\n"]
        symbol_count = 0
        text_lines = code_text.splitlines()

        # Extract title
        title_m = re.search(r"<title>(.*?)</title>", code_text, re.IGNORECASE | re.DOTALL)
        if title_m:
            lines.append(f"📄 Page Title: \"{title_m.group(1).strip()}\"\n")

        lines.append("🏛️ Document Structure, Sections & Landmarks:")
        for lineno, line in enumerate(text_lines, start=1):
            # Section/Nav/Header/Main/Footer/Canvas/Form tags
            for sec_m in re.finditer(r"<(section|header|nav|main|footer|article|aside|form|canvas|dialog)\b([^>]*)>", line, re.IGNORECASE):
                tag = sec_m.group(1).lower()
                attrs = sec_m.group(2)
                id_m = re.search(r'id=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
                id_str = f" id=\"{id_m.group(1)}\"" if id_m else ""
                lines.append(f"  Line {lineno}: <{tag}{id_str}>")
                symbol_count += 1

            # Script functions
            for script_fn_m in re.finditer(r"(?:function\s+([A-Za-z0-9_$]+)|(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", line):
                fn_name = script_fn_m.group(1) or script_fn_m.group(2)
                lines.append(f"  Line {lineno}: ⚡ Script Function: {fn_name}()")
                symbol_count += 1

        return "\n".join(lines).strip(), symbol_count
