"""Test Antigravity-style line diff (+/-) calculation and file/folder tracking."""

import pytest
from pathlib import Path
from app.agent.tools.file_edit_tool import FileEditTool
from app.agent.tools.file_tool import FileWriteTool, set_active_workspace
from app.agent.agent_engine import AIAgentEngine


def test_file_edit_tool_antigravity_diff_stats(tmp_path):
    set_active_workspace(tmp_path)
    try:
        tool = FileEditTool()
        sample_file = tmp_path / "hello.py"
        sample_file.write_text(
            "def greet():\n    print('Hello World')\n    return True\n",
            encoding="utf-8"
        )

        # Replace 1 line with 3 lines -> lines_added=3, lines_removed=1
        target = "    print('Hello World')"
        replacement = "    # Greeting comment\n    print('Hello Antigravity')\n    print('Awesome')"

        res = tool.execute(
            file_path=str(sample_file),
            target_content=target,
            replacement_content=replacement,
            allow_multiple=False,
        )

        assert res.success is True
        assert res.data is not None
        assert res.data["file_name"] == "hello.py"
        assert res.data["lines_added"] == 3
        assert res.data["lines_removed"] == 1
        assert res.data["diff_stat"] == "+3 / -1"
        assert "folder" in res.data
        assert "(+3 / -1 lines)" in res.output
    finally:
        set_active_workspace(None)


def test_file_write_tool_antigravity_diff_stats(tmp_path):
    set_active_workspace(tmp_path)
    try:
        tool = FileWriteTool()
        new_file = tmp_path / "created.py"
        content = "import os\nimport sys\nprint('Done')\n"

        res = tool.execute(file_path=str(new_file), content=content)

        assert res.success is True
        assert res.data is not None
        assert res.data["file_name"] == "created.py"
        assert res.data["lines_added"] == 3
        assert res.data["lines_removed"] == 0
        assert res.data["diff_stat"] == "+3"
        assert res.data["action"] == "created"
        assert "(+3 lines" in res.output
    finally:
        set_active_workspace(None)


def test_agent_engine_diff_summary_card_rendering():
    changes = {
        "C:/project/app/main.py": {
            "file_name": "main.py",
            "folder": "app",
            "lines_added": 14,
            "lines_removed": 3,
            "action": "modified",
        },
        "C:/project/app/ui/chat.py": {
            "file_name": "chat.py",
            "folder": "app/ui",
            "lines_added": 25,
            "lines_removed": 0,
            "action": "created",
        },
    }

    base_output = "Task successfully completed!"
    final_output = AIAgentEngine._include_diff_and_file_summary(base_output, ["C:/project/app/ui/chat.py"], changes)

    assert "### 📝 Code Changes Summary (Antigravity Tracker)" in final_output
    assert "`main.py`" in final_output
    assert "`app`" in final_output
    assert "`+14` / `-3`" in final_output
    assert "`chat.py`" in final_output
    assert "`+25` / `-0`" in final_output
    assert "2 file(s) changed" in final_output
    assert "+39" in final_output
    assert "-3" in final_output
    assert "reviewchanges:latest" in final_output


def test_diff_tracker_singleton():
    from app.agent.diff_tracker import DiffTracker, DiffRecord

    tracker = DiffTracker.instance()
    tracker.clear("test_session")

    tracker.record_change(
        file_path="C:/test/file1.py",
        file_name="file1.py",
        folder="test",
        lines_added=10,
        lines_removed=2,
        action="modified",
        diff_text="@@ -1,2 +1,10 @@",
        session_id="test_session",
    )

    changes = tracker.get_changes("test_session")
    assert len(changes) == 1
    rec = changes[0]
    assert rec.file_name == "file1.py"
    assert rec.lines_added == 10
    assert rec.lines_removed == 2
    assert rec.action == "modified"
    assert rec.diff_text == "@@ -1,2 +1,10 @@"

    # Aggregating another change to the same file
    tracker.record_change(
        file_path="C:/test/file1.py",
        file_name="file1.py",
        folder="test",
        lines_added=5,
        lines_removed=1,
        action="modified",
        diff_text="@@ -10,2 +10,6 @@",
        session_id="test_session",
    )
    changes = tracker.get_changes("test_session")
    assert len(changes) == 1
    assert changes[0].lines_added == 15
    assert changes[0].lines_removed == 3

    tracker.clear("test_session")
    assert len(tracker.get_changes("test_session")) == 0


def test_code_changes_review_dialog(qtbot):
    from app.agent.diff_tracker import DiffRecord
    from app.ui.code_changes_review_dialog import CodeChangesReviewDialog

    records = [
        DiffRecord(
            file_path="C:/test/main.py",
            file_name="main.py",
            folder="app",
            lines_added=8,
            lines_removed=2,
            action="modified",
            diff_text="--- a/main.py\n+++ b/main.py\n@@ -1,2 +1,8 @@\n-old code\n+new code",
        ),
        DiffRecord(
            file_path="C:/test/util.py",
            file_name="util.py",
            folder="utils",
            lines_added=20,
            lines_removed=0,
            action="created",
            diff_text="--- /dev/null\n+++ b/util.py\n@@ -0,0 +1,20 @@\n+print('Hello')",
        ),
    ]

    dialog = CodeChangesReviewDialog(changes=records, theme="dark")
    qtbot.addWidget(dialog)

    assert dialog.file_list.count() == 2
    assert dialog._active_record is not None
    assert dialog._active_record.file_name == "main.py"
    assert "main.py" in dialog.diff_path_label.text()
    assert "+8" in dialog.diff_badge_label.text()

    # Test filtering
    dialog._filter_files("util")
    assert dialog.file_list.item(0).isHidden() is True
    assert dialog.file_list.item(1).isHidden() is False

    dialog._filter_files("")
    assert dialog.file_list.item(0).isHidden() is False
    assert dialog.file_list.item(1).isHidden() is False

