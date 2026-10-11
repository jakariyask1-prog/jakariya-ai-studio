"""Unit tests for Dedicated ToolExecutor (Parts 3, 9)."""

import unittest
import time
from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.tool_executor import ToolExecutor
from app.agent.tools.code_execution_tool import CodeExecutionTool


class DummyDisabledTool(BaseTool):
    def __init__(self):
        super().__init__(name="dummy_disabled", description="Disabled dummy tool")
        self.enabled = False

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(success=True, output="should not run")


class DummyExceptionTool(BaseTool):
    def __init__(self):
        super().__init__(name="dummy_exception", description="Faulty tool")

    def execute(self, **kwargs) -> ToolResult:
        raise ValueError("Simulated tool crash")


class TestAgentToolExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = ToolExecutor(require_user_approval_callback=lambda name, params: True)

    def test_executor_records_execution_time(self):
        tool = CodeExecutionTool()
        result = self.executor.execute_tool(tool, code="print(10 + 20)")
        self.assertTrue(result.success)
        self.assertEqual(result.output.strip(), "30")
        self.assertGreaterEqual(result.execution_time_ms, 0.0)

    def test_executor_rejects_disabled_tool(self):
        tool = DummyDisabledTool()
        result = self.executor.execute_tool(tool)
        self.assertFalse(result.success)
        self.assertIn("currently disabled", result.error)

    def test_executor_captures_unhandled_exceptions(self):
        tool = DummyExceptionTool()
        result = self.executor.execute_tool(tool)
        self.assertFalse(result.success)
        self.assertIn("Simulated tool crash", result.error)

    def test_executor_permission_approval_rejection(self):
        # Callback that denies approval
        denying_executor = ToolExecutor(require_user_approval_callback=lambda name, params: False)
        tool = CodeExecutionTool()
        result = denying_executor.execute_tool(tool, code="print(1)")
        self.assertFalse(result.success)
        self.assertIn("declined by user permission policy", result.error)

    def test_executor_rejects_approval_required_tool_without_handler(self):
        result = ToolExecutor().execute_tool(CodeExecutionTool(), code="print(1)")
        self.assertFalse(result.success)
        self.assertIn("no approval handler", result.error)

    def test_code_execution_terminates_runaway_code(self):
        start = time.perf_counter()
        result = CodeExecutionTool().execute(code="while True: pass", timeout_sec=0.2)
        self.assertFalse(result.success)
        self.assertIn("was terminated", result.error)
        self.assertLess(time.perf_counter() - start, 1.5)


if __name__ == "__main__":
    unittest.main()
