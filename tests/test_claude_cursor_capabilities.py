"""Tests for Claude Code & Cursor-Grade Advanced Autonomous Engineering Capabilities."""

import json
from pathlib import Path
import pytest

from app.agent.tools.file_tool import (
    FileReadTool,
    set_active_workspace,
    get_active_workspace,
)
from app.agent.tools.code_outline_tool import CodeOutlineTool
from app.agent.tools.diagnostics_tool import DiagnosticsTool
from app.agent.tools.git_tool import GitTool
from app.agent.tool_registry import ToolRegistry


@pytest.fixture(autouse=True)
def reset_workspace():
    set_active_workspace(None)
    yield
    set_active_workspace(None)


class TestFileReadSlicing:
    def test_read_file_full_raw_backward_compatible(self, tmp_path):
        f = tmp_path / "sample.py"
        content = "line1\nline2\nline3\nline4\nline5\n"
        f.write_text(content, encoding="utf-8")

        tool = FileReadTool()
        result = tool.execute(file_path=str(f))

        assert result.success is True
        assert result.output == content

    def test_read_file_line_range_slice(self, tmp_path):
        f = tmp_path / "sample.py"
        lines = [f"print('line {i}')" for i in range(1, 21)]
        f.write_text("\n".join(lines), encoding="utf-8")

        tool = FileReadTool()
        result = tool.execute(file_path=str(f), start_line=5, end_line=8)

        assert result.success is True
        assert "5: print('line 5')" in result.output
        assert "8: print('line 8')" in result.output
        assert "print('line 4')" not in result.output
        assert "print('line 9')" not in result.output
        assert "Lines 5-8 of 20" in result.output


class TestCodeOutlineTool:
    def test_outline_python_ast(self, tmp_path):
        f = tmp_path / "calculator.py"
        code = """import math
from typing import Optional

class Calculator:
    \"\"\"A high precision calculator.\"\"\"
    def __init__(self, precision: int = 2):
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        return a + b

    async def compute_async(self, val: float) -> float:
        return val * 2.0

def standalone_helper(x: int) -> int:
    return x * 10
"""
        f.write_text(code, encoding="utf-8")

        tool = CodeOutlineTool()
        result = tool.execute(file_path=str(f))

        assert result.success is True
        assert "Class: Calculator" in result.output
        assert "def __init__(self, precision)" in result.output
        assert "def add(self, a, b) -> float" in result.output
        assert "async def compute_async(self, val) -> float" in result.output
        assert "Function: def standalone_helper(x) -> int" in result.output
        assert "import math" in result.output
        assert result.data["symbols_count"] >= 4

    def test_outline_javascript(self, tmp_path):
        f = tmp_path / "app.js"
        code = """class UserManager {
    constructor() {}
}

export function fetchUsers() {}

const calculateTotal = (a, b) => a + b;
"""
        f.write_text(code, encoding="utf-8")

        tool = CodeOutlineTool()
        result = tool.execute(file_path=str(f))

        assert result.success is True
        assert "UserManager" in result.output
        assert "fetchUsers" in result.output
        assert "calculateTotal" in result.output


class TestDiagnosticsTool:
    def test_diagnostics_python_clean(self, tmp_path):
        f = tmp_path / "valid.py"
        f.write_text("def hello():\n    return 'clean code'\n", encoding="utf-8")

        tool = DiagnosticsTool()
        result = tool.execute(file_path=str(f))

        assert result.success is True
        assert "Syntax Check Passed" in result.output
        assert result.data["status"] == "clean"

    def test_diagnostics_python_syntax_error(self, tmp_path):
        f = tmp_path / "broken.py"
        # Missing colon and invalid indent
        f.write_text("def broken(\nreturn 123\n", encoding="utf-8")

        tool = DiagnosticsTool()
        result = tool.execute(file_path=str(f))

        assert result.success is False
        assert "Syntax Error" in result.error
        assert result.data["status"] == "syntax_error"

    def test_diagnostics_json(self, tmp_path):
        f_valid = tmp_path / "config.json"
        f_valid.write_text('{"name": "test", "active": true}', encoding="utf-8")

        f_invalid = tmp_path / "broken.json"
        f_invalid.write_text('{"name": "test", broken}', encoding="utf-8")

        tool = DiagnosticsTool()
        res_v = tool.execute(file_path=str(f_valid))
        assert res_v.success is True
        assert "JSON Check Passed" in res_v.output

        res_inv = tool.execute(file_path=str(f_invalid))
        assert res_inv.success is False
        assert "JSON Syntax Error" in res_inv.error


class TestGitTool:
    def test_git_tool_non_git_repo(self, tmp_path):
        set_active_workspace(str(tmp_path))

        tool = GitTool()
        result = tool.execute(action="status")

        assert result.success is True
        assert "not currently a Git repository" in result.output

    def test_git_tool_status_and_diff(self, tmp_path):
        import subprocess
        # Initialize a temporary git repo to test git tool actions
        try:
            subprocess.run(["git", "init"], cwd=str(tmp_path), capture_output=True, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(tmp_path), capture_output=True)
            subprocess.run(["git", "config", "user.name", "Tester"], cwd=str(tmp_path), capture_output=True)

            file1 = tmp_path / "test.txt"
            file1.write_text("initial", encoding="utf-8")
            subprocess.run(["git", "add", "test.txt"], cwd=str(tmp_path), capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=str(tmp_path), capture_output=True)

            # Modify file
            file1.write_text("modified", encoding="utf-8")

            set_active_workspace(str(tmp_path))
            tool = GitTool()

            # Status check
            res_status = tool.execute(action="status")
            assert res_status.success is True
            assert "test.txt" in res_status.output

            # Diff check
            res_diff = tool.execute(action="diff")
            assert res_diff.success is True
            assert "+modified" in res_diff.output

        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("Git is not installed or not working in this test environment.")


class TestFull12ToolsRegistry:
    def test_all_12_tools_available(self):
        registry = ToolRegistry(auto_register_defaults=True)
        tools = registry.list_tools()
        assert len(tools) == 12

        tool_names = [t.name for t in tools]
        expected = [
            "read_file",
            "write_file",
            "list_directory",
            "search_files",
            "edit_file",
            "run_command",
            "python_interpreter",
            "web_search",
            "export_document",
            "code_outline",
            "check_diagnostics",
            "git_tool",
        ]
        for exp in expected:
            assert exp in tool_names


class TestMultiLanguageCodingCapabilities:
    @pytest.mark.parametrize("extension,sample_code,target,replacement", [
        (".py", "def add(a, b):\n    return a - b\n", "return a - b", "return a + b"),
        (".html", "<div class=\"old-hero\">\n    <h1>Welcome</h1>\n</div>", "old-hero", "new-modern-hero"),
        (".css", ".container {\n    max-width: 800px;\n    color: red;\n}", "color: red;", "color: #4F46E5;"),
        (".js", "function fetchUser(id) {\n    return api.get('/user/' + id);\n}", "'/user/'", "'/api/v2/users/'"),
        (".jsx", "export default function Header() {\n    return <header className=\"dark\">App</header>;\n}", "className=\"dark\"", "className=\"modern-glass\""),
        (".tsx", "interface Props { title: string; }\nexport const Card: React.FC<Props> = ({ title }) => {\n    return <div>{title}</div>;\n};", "<div>{title}</div>", "<div className=\"card-glow\">{title}</div>"),
        (".php", "<?php\nclass Database {\n    public function connect() {\n        return false;\n    }\n}", "return false;", "return new PDO($dsn);"),
    ])
    def test_read_write_edit_multilanguage_files(self, tmp_path, extension, sample_code, target, replacement):
        from app.agent.tools.file_tool import FileReadTool, FileWriteTool
        from app.agent.tools.file_edit_tool import FileEditTool

        set_active_workspace(str(tmp_path))
        file_path = tmp_path / f"test_file{extension}"

        # 1. Write file
        writer = FileWriteTool()
        w_res = writer.execute(file_path=str(file_path), content=sample_code)
        assert w_res.success is True, f"Failed to write {extension}: {w_res.error}"
        assert file_path.exists()

        # 2. Read file
        reader = FileReadTool()
        r_res = reader.execute(file_path=str(file_path))
        assert r_res.success is True, f"Failed to read {extension}: {r_res.error}"
        assert target in r_res.output

        # 3. Surgical Code Edit / Fix
        editor = FileEditTool()
        e_res = editor.execute(
            file_path=str(file_path),
            target_content=target,
            replacement_content=replacement,
        )
        assert e_res.success is True, f"Failed to edit {extension}: {e_res.error}"

        # 4. Verify fixed content
        fixed_text = file_path.read_text(encoding="utf-8")
        assert replacement in fixed_text
        assert target not in fixed_text

    def test_relative_workspace_file_edit_and_read(self, tmp_path):
        from app.agent.tools.file_tool import FileReadTool, FileWriteTool
        from app.agent.tools.file_edit_tool import FileEditTool

        set_active_workspace(str(tmp_path))
        sub = tmp_path / "pkg"
        sub.mkdir()
        target_f = sub / "module.py"
        target_f.write_text("VALUE = 100\n", encoding="utf-8")

        # Edit using relative path
        editor = FileEditTool()
        e_res = editor.execute(
            file_path="pkg/module.py",
            target_content="VALUE = 100",
            replacement_content="VALUE = 200",
        )
        assert e_res.success is True, f"Relative edit failed: {e_res.error}"

        # Read using relative path
        reader = FileReadTool()
        r_res = reader.execute(file_path="pkg/module.py")
        assert r_res.success is True, f"Relative read failed: {r_res.error}"
        assert "VALUE = 200" in r_res.output

    def test_crlf_target_content_tolerance(self, tmp_path):
        from app.agent.tools.file_edit_tool import FileEditTool

        set_active_workspace(str(tmp_path))
        target_f = tmp_path / "sample.py"
        target_f.write_text("def hello():\n    return 42\n", encoding="utf-8")

        editor = FileEditTool()
        # CRLF target content provided to an LF file
        res = editor.execute(
            file_path="sample.py",
            target_content="def hello():\r\n    return 42",
            replacement_content="def hello():\n    return 99",
        )
        assert res.success is True, f"CRLF tolerance failed: {res.error}"
        assert "return 99" in target_f.read_text(encoding="utf-8")

    def test_tool_registry_aliases_antigravity_cursor_claude(self):
        reg = ToolRegistry()
        # Antigravity tool names
        assert reg.get_tool("view_file") is not None
        assert reg.get_tool("replace_file_content") is not None
        # Claude Code & Shell names
        assert reg.get_tool("terminal") is not None
        assert reg.get_tool("grep") is not None
        assert reg.get_tool("outline") is not None
        assert reg.get_tool("diagnostics") is not None

    def test_parse_tool_call_json_and_aliases(self):
        from app.agent.agent_engine import AIAgentEngine
        engine = AIAgentEngine()

        # Action: view_file with JSON input
        c1 = engine._parse_tool_call('Action: view_file\nAction Input: {"file_path": "main.py"}')
        assert c1 == ("read_file", {"file_path": "main.py"})

        # Action: `replace_file_content` with backticks
        c2 = engine._parse_tool_call('Action: `replace_file_content`\nAction Input: {"file_path": "x.py", "target_content": "1", "replacement_content": "2"}')
        assert c2 is not None and c2[0] == "edit_file"

        # Direct JSON format
        c3 = engine._parse_tool_call('{"action": "view_file", "parameters": {"file_path": "test.py"}}')
        assert c3 == ("read_file", {"file_path": "test.py"})

