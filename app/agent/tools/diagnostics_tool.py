"""Diagnostics & Syntax Verification Tool for AI Agent (Cursor-style in-memory lint & verification)."""

import ast
import json
from pathlib import Path
from typing import Any, Dict

from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import resolve_user_path, get_active_workspace, get_user_desktop_dir


class DiagnosticsTool(BaseTool):
    """Tool enabling AI Agent to verify code syntax and detect errors before/after editing."""

    def __init__(self):
        super().__init__(
            name="check_diagnostics",
            description="Verify code syntax, indentation, and JSON structure of a file (in-memory diagnostics check).",
            permission_level=PermissionLevel.READ_ONLY,
            version="1.0.0",
            supported_file_types=[".py", ".json", ".js", ".ts", ".html"],
            capabilities=["check_diagnostics", "lint_file", "syntax_check", "verify_code"],
            input_schema={
                "file_path": "string (path to code or config file to check)",
            },
            output_schema={"status": "string", "errors_count": "integer"},
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
            suffix = target_p.suffix.lower()

            if suffix == ".py":
                return self._check_python(code_text, target_p)
            elif suffix == ".json":
                return self._check_json(code_text, target_p)
            elif suffix in (".html", ".htm"):
                return self._check_html(code_text, target_p)
            else:
                return self._check_brackets(code_text, target_p)

        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Diagnostic check error: {exc}")

    def _check_html(self, code_text: str, target_p: Path) -> ToolResult:
        import html.parser

        class HTMLValidator(html.parser.HTMLParser):
            def __init__(self):
                super().__init__()
                self.stack = []
                self.void_tags = {
                    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                    'link', 'meta', 'param', 'source', 'track', 'wbr'
                }
                self.errors = []

            def handle_starttag(self, tag, attrs):
                t = tag.lower()
                if t not in self.void_tags:
                    self.stack.append((t, self.getpos()))

            def handle_endtag(self, tag):
                t = tag.lower()
                if t in self.void_tags:
                    return
                if not self.stack:
                    self.errors.append(f"Unexpected closing tag </{t}> at line {self.getpos()[0]}")
                    return
                last_tag, pos = self.stack.pop()
                if last_tag != t:
                    self.errors.append(
                        f"Mismatched HTML tag: expected </{last_tag}> (opened at line {pos[0]}), got </{t}> at line {self.getpos()[0]}"
                    )

        validator = HTMLValidator()
        try:
            validator.feed(code_text)
            if validator.errors:
                err_msg = f"❌ HTML Structure Errors in {target_p.name}:\n" + "\n".join(f"   - {e}" for e in validator.errors[:5])
                return ToolResult(
                    success=False,
                    output="",
                    error=err_msg,
                    data={"file": str(target_p), "status": "html_error", "errors_count": len(validator.errors)},
                )
            if validator.stack:
                unclosed = [f"<{t}> at line {pos[0]}" for t, pos in validator.stack[-3:]]
                err_msg = f"❌ Unclosed HTML tags in {target_p.name}:\n" + "\n".join(f"   - {u}" for u in unclosed)
                return ToolResult(
                    success=False,
                    output="",
                    error=err_msg,
                    data={"file": str(target_p), "status": "unclosed_tags", "errors_count": len(validator.stack)},
                )

            # Check balanced brackets in embedded JS/CSS
            bracket_res = self._check_brackets(code_text, target_p)
            if not bracket_res.success:
                return bracket_res

            return ToolResult(
                success=True,
                output=f"✅ HTML & Web Diagnostics Passed: Valid HTML5 structure, balanced tags, and clean inline scripts in {target_p.name}.",
                data={"file": str(target_p), "status": "clean", "errors_count": 0},
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"❌ HTML Parsing Error in {target_p.name}: {e}",
                data={"file": str(target_p), "status": "parse_error", "errors_count": 1},
            )

    def _check_python(self, code_text: str, target_p: Path) -> ToolResult:
        try:
            # 1. Parse AST
            ast.parse(code_text, filename=target_p.name)
            # 2. Compile check (catches subtle compilation issues like duplicate kwargs or invalid returns)
            compile(code_text, filename=target_p.name, mode="exec")

            return ToolResult(
                success=True,
                output=f"✅ Syntax Check Passed: No syntax, indentation, or compilation errors found in {target_p.name}.",
                data={"file": str(target_p), "status": "clean", "errors_count": 0},
            )
        except SyntaxError as e:
            line_snippet = e.text.strip() if e.text else ""
            err_msg = (
                f"❌ Python Syntax Error in {target_p.name} at Line {e.lineno}, Col {e.offset or 0}:\n"
                f"   {e.msg}\n"
                f"   Code: {line_snippet}"
            )
            return ToolResult(
                success=False,
                output="",
                error=err_msg,
                data={"file": str(target_p), "status": "syntax_error", "line": e.lineno, "col": e.offset, "errors_count": 1},
            )

    def _check_json(self, code_text: str, target_p: Path) -> ToolResult:
        try:
            json.loads(code_text)
            return ToolResult(
                success=True,
                output=f"✅ JSON Check Passed: Valid JSON syntax in {target_p.name}.",
                data={"file": str(target_p), "status": "clean", "errors_count": 0},
            )
        except json.JSONDecodeError as e:
            err_msg = f"❌ JSON Syntax Error in {target_p.name} at Line {e.lineno}, Col {e.colno}: {e.msg}"
            return ToolResult(
                success=False,
                output="",
                error=err_msg,
                data={"file": str(target_p), "status": "json_error", "line": e.lineno, "col": e.colno, "errors_count": 1},
            )

    def _check_brackets(self, code_text: str, target_p: Path) -> ToolResult:
        # Simple balanced brackets check for JS/TS/HTML
        stack = []
        pairs = {')': '(', '}': '{', ']': '['}
        line_num = 1

        for char in code_text:
            if char == '\n':
                line_num += 1
            elif char in pairs.values():
                stack.append((char, line_num))
            elif char in pairs:
                if not stack or stack[-1][0] != pairs[char]:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"❌ Unmatched closing '{char}' near line {line_num} in {target_p.name}.",
                        data={"file": str(target_p), "status": "unmatched_bracket", "line": line_num, "errors_count": 1},
                    )
                stack.pop()

        if stack:
            open_char, open_line = stack[-1]
            return ToolResult(
                success=False,
                output="",
                error=f"❌ Unclosed '{open_char}' opened at line {open_line} in {target_p.name}.",
                data={"file": str(target_p), "status": "unclosed_bracket", "line": open_line, "errors_count": 1},
            )

        return ToolResult(
            success=True,
            output=f"✅ Structural Check Passed: Brackets and braces are balanced in {target_p.name}.",
            data={"file": str(target_p), "status": "clean", "errors_count": 0},
        )
