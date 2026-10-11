import os
from pathlib import Path
from app.agent.tools.file_tool import FileWriteTool, FileReadTool, resolve_user_path
from app.agent.tools.base_tool import ToolResult

def test_full_agent_desktop_workflow(tmp_path, monkeypatch):
    # Do not write to the real Windows Desktop: it may be redirected or
    # protected in automated environments.
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / "Desktop").mkdir()
    # 1. Test Path Resolution
    resolved_path = resolve_user_path("hello.txt")
    expected_path = Path.home() / "Desktop" / "hello.txt"
    assert resolved_path == expected_path

    # 2. Test FileWriteTool
    write_tool = FileWriteTool()
    test_content = "Hello! This is a test file created by Jakariya AI Studio Agent."
    
    # Cleanup prior
    if expected_path.exists():
        expected_path.unlink()

    try:
        result: ToolResult = write_tool.execute(file_path="hello.txt", content=test_content)
        assert result.success is True
        assert expected_path.exists()
        assert expected_path.read_text(encoding="utf-8") == test_content

        # 3. Test FileReadTool
        read_tool = FileReadTool()
        read_result: ToolResult = read_tool.execute(file_path="hello.txt")
        assert read_result.success is True
        assert read_result.output == test_content
    finally:
        if expected_path.exists():
            expected_path.unlink()
