"""Tests for Antigravity-Style Agent Tools & Workspace Functionality."""

import os
from pathlib import Path
import pytest

from app.agent.tools.directory_list_tool import DirectoryListTool
from app.agent.tools.file_search_tool import FileSearchTool
from app.agent.tools.file_edit_tool import FileEditTool
from app.agent.tools.terminal_tool import TerminalCommandTool
from app.agent.tools.file_tool import (
    set_active_workspace,
    get_active_workspace,
    get_allowed_agent_write_roots,
    resolve_agent_write_path,
)
from app.agent.tool_registry import ToolRegistry


@pytest.fixture(autouse=True)
def reset_workspace():
    """Ensure workspace is reset before and after each test."""
    set_active_workspace(None)
    yield
    set_active_workspace(None)


class TestDirectoryListTool:
    def test_list_directory_basic(self, tmp_path):
        # Create some nested files
        sub = tmp_path / "src"
        sub.mkdir()
        (sub / "main.py").write_text("print('hello')", encoding="utf-8")
        (sub / "utils.py").write_text("def add(a, b): return a + b", encoding="utf-8")
        (tmp_path / "README.md").write_text("# Test Project", encoding="utf-8")

        tool = DirectoryListTool()
        result = tool.execute(folder_path=str(tmp_path))

        assert result.success is True
        assert "README.md" in result.output
        assert "main.py" in result.output
        assert "utils.py" in result.output
        assert result.data["file_count"] == 3
        assert result.data["dir_count"] == 1

    def test_list_directory_ignores_junk_folders(self, tmp_path):
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        (git_dir / "config").write_text("git config", encoding="utf-8")

        venv_dir = tmp_path / ".venv"
        venv_dir.mkdir()
        (venv_dir / "pyvenv.cfg").write_text("venv config", encoding="utf-8")

        src = tmp_path / "app"
        src.mkdir()
        (src / "app.py").write_text("code", encoding="utf-8")

        tool = DirectoryListTool()
        result = tool.execute(folder_path=str(tmp_path))

        assert result.success is True
        assert "app.py" in result.output
        assert ".git" not in result.output
        assert ".venv" not in result.output

    def test_list_directory_active_workspace_default(self, tmp_path):
        (tmp_path / "project_marker.txt").write_text("active", encoding="utf-8")
        set_active_workspace(str(tmp_path))

        tool = DirectoryListTool()
        result = tool.execute(folder_path="")

        assert result.success is True
        assert "project_marker.txt" in result.output


class TestFileSearchTool:
    def test_search_files_keyword(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "a.py").write_text("def calculate_total():\n    return 42\n", encoding="utf-8")
        (src / "b.py").write_text("def helper():\n    total = calculate_total()\n", encoding="utf-8")
        (src / "c.txt").write_text("unrelated note", encoding="utf-8")

        tool = FileSearchTool()
        result = tool.execute(query="calculate_total", folder_path=str(tmp_path))

        assert result.success is True
        assert result.data["total_matches"] == 2
        assert "a.py" in result.output
        assert "Line 1" in result.output
        assert "b.py" in result.output
        assert "Line 2" in result.output

    def test_search_files_with_pattern(self, tmp_path):
        (tmp_path / "test.py").write_text("SECRET_KEY = 123", encoding="utf-8")
        (tmp_path / "test.md").write_text("SECRET_KEY = 456", encoding="utf-8")

        tool = FileSearchTool()
        result = tool.execute(query="SECRET_KEY", folder_path=str(tmp_path), file_pattern="*.py")

        assert result.success is True
        assert "test.py" in result.output
        assert "test.md" not in result.output

    def test_search_files_empty_query(self, tmp_path):
        tool = FileSearchTool()
        result = tool.execute(query="", folder_path=str(tmp_path))
        assert result.success is False
        assert "empty" in result.error.lower()


class TestFileEditTool:
    def test_edit_file_surgical_replacement(self, tmp_path):
        set_active_workspace(str(tmp_path))
        target_file = tmp_path / "script.py"
        target_file.write_text("def greeting():\n    return 'Hello World'\n", encoding="utf-8")

        tool = FileEditTool()
        result = tool.execute(
            file_path=str(target_file),
            target_content="return 'Hello World'",
            replacement_content="return 'Hello Antigravity'",
        )

        assert result.success is True
        assert target_file.read_text(encoding="utf-8") == "def greeting():\n    return 'Hello Antigravity'\n"

    def test_edit_file_target_not_found(self, tmp_path):
        set_active_workspace(str(tmp_path))
        target_file = tmp_path / "script.py"
        target_file.write_text("print('abc')", encoding="utf-8")

        tool = FileEditTool()
        result = tool.execute(
            file_path=str(target_file),
            target_content="def non_existent():",
            replacement_content="pass",
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_edit_file_multiple_occurrences(self, tmp_path):
        set_active_workspace(str(tmp_path))
        target_file = tmp_path / "repeat.txt"
        target_file.write_text("foo bar foo baz foo", encoding="utf-8")

        tool = FileEditTool()
        # Default allow_multiple=False should reject ambiguous match
        result = tool.execute(
            file_path=str(target_file),
            target_content="foo",
            replacement_content="qux",
            allow_multiple=False,
        )
        assert result.success is False
        assert "occurs 3 times" in result.error.lower()

        # With allow_multiple=True should succeed
        result2 = tool.execute(
            file_path=str(target_file),
            target_content="foo",
            replacement_content="qux",
            allow_multiple=True,
        )
        assert result2.success is True
        assert target_file.read_text(encoding="utf-8") == "qux bar qux baz qux"


class TestTerminalCommandTool:
    def test_run_command_safe(self, tmp_path):
        tool = TerminalCommandTool()
        result = tool.execute(
            command='python -c "print(10 + 25)"',
            cwd=str(tmp_path),
        )

        assert result.success is True
        assert "35" in result.output
        assert result.data["exit_code"] == 0

    def test_run_command_blocks_dangerous(self):
        tool = TerminalCommandTool()
        result = tool.execute(command="del /s /q c:\\windows")
        assert result.success is False
        assert "safety policy" in result.error.lower()

    def test_run_command_empty(self):
        tool = TerminalCommandTool()
        result = tool.execute(command="")
        assert result.success is False
        assert "empty" in result.error.lower()


class TestWorkspaceSecurityAndResolution:
    def test_workspace_included_in_allowed_roots(self, tmp_path):
        assert tmp_path not in get_allowed_agent_write_roots()
        set_active_workspace(str(tmp_path))
        assert tmp_path in get_allowed_agent_write_roots()

    def test_resolve_agent_write_path_in_workspace(self, tmp_path):
        set_active_workspace(str(tmp_path))
        target = tmp_path / "subdir" / "code.py"
        resolved = resolve_agent_write_path(str(target))
        assert resolved == target.resolve()


class TestToolRegistryIntegration:
    def test_tools_registered(self):
        registry = ToolRegistry()
        tool_names = [t.name for t in registry.list_tools()]
        assert "list_directory" in tool_names
        assert "search_files" in tool_names
        assert "edit_file" in tool_names
        assert "run_command" in tool_names


class TestInputBarWorkspace:
    def test_set_and_clear_workspace(self, qtbot, tmp_path):
        from app.ui.input_bar import InputBar
        bar = InputBar()
        qtbot.addWidget(bar)
        bar.show()

        assert bar.get_active_workspace() is None
        assert not bar.workspace_widget.isVisible()

        # Set workspace folder
        bar.set_workspace_folder(str(tmp_path))
        assert bar.get_active_workspace() == str(tmp_path)
        assert bar.workspace_widget.isVisible() is True
        assert bar.is_agent_mode_active() is True

        # Clear workspace
        bar.clear_workspace_folder()
        assert bar.get_active_workspace() is None
        assert not bar.workspace_widget.isVisible()

    def test_folder_button_enable_disable(self, qtbot):
        from app.ui.input_bar import InputBar
        bar = InputBar()
        qtbot.addWidget(bar)

        bar.disable()
        assert bar.folder_button.isEnabled() is False

        bar.enable()
        assert bar.folder_button.isEnabled() is True
