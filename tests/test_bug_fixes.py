import os
from pathlib import Path
import pytest

from app.agent.tools.file_tool import FileWriteTool, FileReadTool, resolve_user_path
from app.agent.tools.base_tool import ToolResult


def test_resolve_user_path_desktop_single_file():
    resolved = resolve_user_path("hello.txt")
    expected = Path.home() / "Desktop" / "hello.txt"
    assert resolved == expected


def test_resolve_user_path_desktop_folder():
    resolved = resolve_user_path("Desktop/hello.txt")
    expected = Path.home() / "Desktop" / "hello.txt"
    assert resolved == expected


def test_resolve_user_path_documents_folder():
    resolved = resolve_user_path("Documents/notes.txt")
    expected = Path.home() / "Documents" / "notes.txt"
    assert resolved == expected


def test_resolve_user_path_downloads_folder():
    resolved = resolve_user_path("Downloads/data.csv")
    expected = Path.home() / "Downloads" / "data.csv"
    assert resolved == expected


def test_file_write_tool_creates_file_on_desktop(tmp_path, monkeypatch):
    """The file tool should work with the resolved Desktop path.

    The real Desktop can be a protected or redirected Windows folder in CI, so
    redirect ``Path.home`` to a temporary user profile for this integration
    test instead of writing to a developer's actual Desktop.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Desktop").mkdir()
    tool = FileWriteTool()
    test_filename = "jakariya_test_auto_desktop.txt"
    test_content = "Automated test content for Desktop path resolution."
    
    expected_path = Path.home() / "Desktop" / test_filename
    
    # Cleanup prior to test if exists
    if expected_path.exists():
        expected_path.unlink()

    try:
        res: ToolResult = tool.execute(file_path=test_filename, content=test_content)
        assert res.success is True
        assert expected_path.exists()
        assert expected_path.read_text(encoding="utf-8") == test_content
    finally:
        if expected_path.exists():
            expected_path.unlink()


def test_file_read_tool_reads_file_from_desktop(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Desktop").mkdir()
    write_tool = FileWriteTool()
    read_tool = FileReadTool()
    
    test_filename = "jakariya_test_read_desktop.txt"
    test_content = "Content to read from Desktop."
    expected_path = Path.home() / "Desktop" / test_filename

    if expected_path.exists():
        expected_path.unlink()

    try:
        write_res = write_tool.execute(file_path=test_filename, content=test_content)
        assert write_res.success is True
        
        read_res = read_tool.execute(file_path=test_filename)
        assert read_res.success is True
        assert read_res.output == test_content
    finally:
        if expected_path.exists():
            expected_path.unlink()
