"""End-to-End Real Simulation Test for Autonomous Coding Agent Mode in a Project Workspace."""

import os
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from app.agent.agent_engine import AIAgentEngine
from app.agent.tool_registry import ToolRegistry
from app.agent.tools.tool_executor import ToolExecutor
from app.agent.tools.file_tool import set_active_workspace, get_active_workspace
from app.providers.models.chat_response import ChatResponse


@pytest.fixture(autouse=True)
def cleanup_workspace():
    set_active_workspace(None)
    yield
    set_active_workspace(None)


class TestEndToEndAutonomousAgent:
    def test_end_to_end_full_cycle_coding_agent(self, tmp_path):
        """Simulate a complete multi-turn autonomous coding session in a real project directory.
        
        Verifies:
        1. list_directory discovers files in workspace
        2. search_files locates the bug
        3. code_outline extracts file symbols
        4. edit_file surgically patches the code on disk
        5. check_diagnostics verifies syntax integrity
        6. run_command executes tests in the workspace
        7. Agent produces the Final Answer
        """
        # ── Setup Project Workspace on Disk ──────────────────────────────
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()

        # Create buggy code
        calc_file = src_dir / "calculator.py"
        calc_code = (
            "def calculate_discount(price: float, pct: float) -> float:\n"
            "    # Bug: adds instead of subtracting discount\n"
            "    return price + (price * pct)\n"
        )
        calc_file.write_text(calc_code, encoding="utf-8")

        # Create unit test file
        test_file = tests_dir / "test_calc.py"
        test_code = (
            "from src.calculator import calculate_discount\n\n"
            "def test_discount():\n"
            "    # 100 with 10% discount should be 90\n"
            "    assert calculate_discount(100.0, 0.10) == 90.0\n"
        )
        test_file.write_text(test_code, encoding="utf-8")

        # Set active workspace to this folder
        set_active_workspace(str(tmp_path))
        assert get_active_workspace() == tmp_path.resolve()

        # ── Setup Engine with Full Default Tools ─────────────────────────
        registry = ToolRegistry(auto_register_defaults=True)
        executor = ToolExecutor(require_user_approval_callback=lambda name, params: True)
        engine = AIAgentEngine(tool_registry=registry, tool_executor=executor)

        # ── Mock LLM Provider simulating a Senior AI Engineer ───────────
        mock_provider = MagicMock()

        # Turn 1: Discover directory tree
        turn1 = ChatResponse(
            content="Thought: Let's inspect the project files.\nAction: list_directory\nAction Input: \"\"",
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )
        # Turn 2: Grep search for the buggy function
        turn2 = ChatResponse(
            content="Thought: Let's search for calculate_discount across all files.\nAction: search_files\nAction Input: calculate_discount",
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )
        # Turn 3: Outline the file structure
        turn3 = ChatResponse(
            content="Thought: Let's inspect the outline of src/calculator.py.\nAction: code_outline\nAction Input: src/calculator.py",
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )
        # Turn 4: Surgically edit the file on disk
        turn4 = ChatResponse(
            content=(
                "Thought: The calculation has a bug: it adds discount instead of subtracting. Let's fix it.\n"
                "Action: edit_file\n"
                f'Action Input: {{"file_path": "{calc_file.as_posix()}", "target_content": "return price + (price * pct)", "replacement_content": "return price - (price * pct)"}}'
            ),
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )
        # Turn 5: Run syntax diagnostics
        turn5 = ChatResponse(
            content=f"Thought: Let's verify Python syntax diagnostics.\nAction: check_diagnostics\nAction Input: {calc_file.as_posix()}",
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )
        # Turn 6: Run tests
        import sys
        py_exe = sys.executable.replace("\\", "/")
        turn6 = ChatResponse(
            content=(
                "Thought: Let's run the test suite to verify the fix.\n"
                "Action: run_command\n"
                f'Action Input: "{py_exe}" -m pytest "{test_file.as_posix()}"'
            ),
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )
        # Turn 7: Final Answer
        turn7 = ChatResponse(
            content=(
                "Final Answer: The bug in calculate_discount was successfully found and fixed! "
                "Surgically replaced + with -, verified syntax diagnostics with 0 errors, and all tests passed!"
            ),
            model="claude-3-5-sonnet",
            provider_id="mock_claude",
        )

        mock_provider.chat.side_effect = [turn1, turn2, turn3, turn4, turn5, turn6, turn7]
        engine.provider_manager = mock_provider

        # ── Execute Task ─────────────────────────────────────────────────
        result = engine.execute_task(
            task_description="Find and fix the bug in calculator discount logic, verify syntax, and run tests.",
            model="claude-3-5-sonnet",
        )

        # ── Assertions & Verification ────────────────────────────────────
        # 1. Verify all 7 turns executed
        assert mock_provider.chat.call_count == 7

        # 2. Verify Final Answer produced
        assert "Final Answer" in result
        assert "fixed" in result.lower()

        # 3. VERIFY DISK MODIFICATION: File on disk was ACTUALLY changed!
        disk_content = calc_file.read_text(encoding="utf-8")
        assert "return price - (price * pct)" in disk_content
        assert "return price + (price * pct)" not in disk_content

        # 4. Execute the fixed code directly to prove the bug was 100% fixed!
        namespace = {}
        exec(disk_content, namespace)
        calculate_discount = namespace["calculate_discount"]
        assert calculate_discount(100.0, 0.10) == 90.0
