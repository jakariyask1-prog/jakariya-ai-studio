"""Comprehensive Integration Tests for Production-Ready Phase 9 Agent Platform (Parts 1-8)."""

import unittest
import time
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

from app.agent.tools.base_tool import PermissionLevel, ToolResult
from app.agent.tools.file_tool import FileReadTool, FileWriteTool
from app.agent.tools.code_execution_tool import CodeExecutionTool
from app.agent.tools.web_search_tool import WebSearchTool
from app.agent.tool_registry import ToolRegistry
from app.agent.tools.tool_executor import ToolExecutor
from app.agent.tools.tool_cache import ToolCache
from app.agent.tools.timeout_manager import TimeoutManager
from app.agent.task.task_manager import TaskManager
from app.agent.task.task_state import TaskState
from app.agent.agent_engine import AIAgentEngine
from app.providers.models.chat_response import ChatResponse


class TestAgentProductionReady(unittest.TestCase):
    def test_part_1_approval_dialog_integration_callback(self):
        # Deny callback
        executor_deny = ToolExecutor(require_user_approval_callback=lambda name, params: False)
        write_tool = FileWriteTool()
        result_deny = executor_deny.execute_tool(write_tool, file_path="/tmp/test.txt", content="sample")
        self.assertFalse(result_deny.success)
        self.assertIn("declined by user permission policy", result_deny.error)

        # Allow callback
        executor_allow = ToolExecutor(require_user_approval_callback=lambda name, params: True)
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", classmethod(lambda cls: Path(tmpdir))):
                (Path.home() / "Desktop").mkdir()
                result_allow = executor_allow.execute_tool(
                    write_tool,
                    file_path="approved.txt",
                    content="approved",
                )
                self.assertTrue(result_allow.success)

    def test_part_2_task_cancellation(self):
        mgr = TaskManager()
        engine = AIAgentEngine(task_manager=mgr)
        original_start_task = mgr.start_task

        def cancel_after_start(plan):
            original_start_task(plan)
            mgr.cancel_task()

        mgr.start_task = cancel_after_start

        mock_provider = MagicMock()
        mock_provider.chat.return_value = ChatResponse(content="Task in progress", model="mock", provider_id="mock")
        engine.provider_manager = mock_provider

        output = engine.execute_task("Run calculation task")
        self.assertEqual(output, "Task Cancelled.")

    def test_part_3_timeout_manager_enforcement(self):
        tm = TimeoutManager(tool_timeout_sec=0.1)

        def slow_func():
            import time
            time.sleep(0.5)
            return "done"

        start = time.perf_counter()
        with self.assertRaises(TimeoutError):
            tm.run_with_timeout(slow_func, timeout_sec=0.1, op_name="Slow Operation")
        self.assertLess(time.perf_counter() - start, 0.3)

    def test_part_4_tool_cache_safety(self):
        cache = ToolCache(default_ttl_sec=60)
        read_tool = FileReadTool()
        write_tool = FileWriteTool()

        res_read = ToolResult(success=True, output="File data")
        res_write = ToolResult(success=True, output="Saved data")

        # File reads require explicit approval and must not be cached.
        cache.set(read_tool, {"file_path": "data.txt"}, res_read)
        hit_read = cache.get(read_tool, file_path="data.txt")
        self.assertIsNone(hit_read)

        # Caching write_file (Requires Approval / Write) -> Rejected by safety policy
        cache.set(write_tool, {"file_path": "data.txt", "content": "x"}, res_write)
        hit_write = cache.get(write_tool, file_path="data.txt", content="x")
        self.assertIsNone(hit_write)

    def test_part_6_real_world_end_to_end_scenarios(self):
        # Scenario 1: Calculator
        code_tool = CodeExecutionTool()
        res_calc = code_tool.execute(code="print(100 * 5)")
        self.assertTrue(res_calc.success)
        self.assertEqual(res_calc.output.strip(), "500")

        # Scenario 2: File Reader
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = str(Path(tmpdir) / "read_me.txt")
            Path(fpath).write_text("Hello Production", encoding="utf-8")
            read_tool = FileReadTool()
            res_read = read_tool.execute(file_path=fpath)
            self.assertTrue(res_read.success)
            self.assertEqual(res_read.output, "Hello Production")

    def test_progress_callback_is_used_during_agent_execution(self):
        engine = AIAgentEngine(task_manager=TaskManager())
        progress_messages = []

        mock_provider = MagicMock()
        mock_provider.chat.return_value = ChatResponse(content="Final Answer: done", model="mock", provider_id="mock")
        engine.provider_manager = mock_provider

        engine.execute_task(
            "Summarize this task",
            progress_callback=lambda progress: progress_messages.append(progress.message),
        )

        self.assertTrue(progress_messages)
        self.assertIn("Task started", progress_messages[0])


if __name__ == "__main__":
    unittest.main()
