"""Unit and Integration tests for AI Agent Framework, ReAct Engine & Task Planner (Phase 9 Step 1 & 2)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication
from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tools.file_tool import FileReadTool, FileWriteTool
from app.agent.tools.code_execution_tool import CodeExecutionTool
from app.agent.tools.web_search_tool import WebSearchTool
from app.agent.tools.tool_executor import ToolExecutor
from app.agent.tool_registry import ToolRegistry
from app.agent.agent_engine import AIAgentEngine
from app.agent.agent_worker import APPROVAL_TIMEOUT_SECONDS, AgentWorker
from app.agent.planner.task_planner import TaskPlanner
from app.providers.models.chat_response import ChatResponse

_APP = QApplication.instance() or QApplication([])


class TestAIAgentFramework(unittest.TestCase):
    """Test suite for Phase 9 Autonomous AI Agent Framework."""

    def test_file_write_and_read_tools_with_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(Path, "home", classmethod(lambda cls: Path(tmpdir))):
                (Path.home() / "Desktop").mkdir()
                file_path = "test_agent_file.txt"
                write_tool = FileWriteTool()
                self.assertEqual(write_tool.permission_level, PermissionLevel.REQUIRES_APPROVAL)
                self.assertTrue(write_tool.requires_approval())

                res_write = write_tool.execute(file_path=file_path, content="Hello Agent")
                self.assertTrue(res_write.success)
                self.assertIn("Successfully wrote", res_write.output)

                read_tool = FileReadTool()
                self.assertEqual(read_tool.permission_level, PermissionLevel.REQUIRES_APPROVAL)
                self.assertTrue(read_tool.requires_approval())

                res_read = read_tool.execute(file_path=file_path)
                self.assertTrue(res_read.success)
                self.assertEqual(res_read.output, "Hello Agent")

    def test_code_execution_tool_permissions(self):
        code_tool = CodeExecutionTool()
        self.assertEqual(code_tool.permission_level, PermissionLevel.REQUIRES_APPROVAL)
        self.assertTrue(code_tool.requires_approval())

        code = "print(21 + 21)"
        res = code_tool.execute(code=code)
        self.assertTrue(res.success)
        self.assertEqual(res.output.strip(), "42")

    def test_web_search_tool_permissions(self):
        search_tool = WebSearchTool()
        self.assertEqual(search_tool.permission_level, PermissionLevel.READ_ONLY)
        self.assertFalse(search_tool.requires_approval())

    def test_tool_approval_timeout_allows_time_to_review(self):
        self.assertEqual(APPROVAL_TIMEOUT_SECONDS, 300)

    def test_exact_task_action_approval_skips_only_the_same_action(self):
        worker = AgentWorker()
        params = {"file_path": "report.pdf", "content": "safe content"}
        fingerprint = worker._approval_fingerprint("export_document", params)
        with worker._approval_lock:
            worker._approved_actions.add(fingerprint)

        self.assertTrue(worker._ask_user_approval("export_document", params))

    def test_task_wide_auto_approval_skips_all_actions_for_task(self):
        worker = AgentWorker()
        worker.enable_auto_approval_for_task()

        self.assertTrue(worker._ask_user_approval("export_document", {"file_path": "a.pdf"}))
        self.assertTrue(worker._ask_user_approval("write_file", {"file_path": "b.txt"}))
        self.assertTrue(worker._ask_user_approval("run_command", {"command": "echo test"}))

    def test_tool_approval_dialog_allow_all_properties(self):
        from app.ui.approval_dialog import ToolApprovalDialog
        dialog = ToolApprovalDialog(
            tool_name="write_file",
            tool_description="Write file test",
            params={"file_path": "test.txt"},
        )
        self.assertFalse(dialog.is_allow_all)
        dialog._allow_all = True
        self.assertTrue(dialog.is_allow_all)
        dialog._allow_all = False
        dialog.remember_for_task.setChecked(True)
        self.assertTrue(dialog.is_allow_all)

    def test_agent_preserves_image_attachment_for_vision_provider(self):
        agent = AIAgentEngine()
        mock_provider = MagicMock()
        mock_provider.chat.return_value = ChatResponse(
            content="Final Answer: I created the requested document.",
            model="mock-model",
            provider_id="mock-provider",
        )
        agent.provider_manager = mock_provider
        attachment_payload = [
            {"type": "text", "text": "Create a DOCX using the attached image as the template."},
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "abc"}},
        ]

        response = agent.execute_task(attachment_payload, model="mock-model")

        self.assertIn("Final Answer", response)
        request = mock_provider.chat.call_args.args[0]
        self.assertEqual(request.messages[-1].content, attachment_payload)

    def test_tool_registry_auto_registration_and_filtering(self):
        registry = ToolRegistry(auto_register_defaults=True)
        all_tools = registry.list_tools()
        self.assertEqual(len(all_tools), 12)

        read_only_tools = registry.list_tools(permission_filter=PermissionLevel.READ_ONLY)
        self.assertEqual(len(read_only_tools), 6)
        tool_names = [t.name for t in read_only_tools]
        self.assertIn("web_search", tool_names)
        self.assertIn("list_directory", tool_names)
        self.assertIn("search_files", tool_names)
        self.assertIn("code_outline", tool_names)
        self.assertIn("check_diagnostics", tool_names)
        self.assertIn("git_tool", tool_names)

        approval_tools = registry.list_tools(permission_filter=PermissionLevel.REQUIRES_APPROVAL)
        self.assertEqual(len(approval_tools), 6)
        approval_names = [t.name for t in approval_tools]
        self.assertIn("read_file", approval_names)
        self.assertIn("write_file", approval_names)
        self.assertIn("python_interpreter", approval_names)
        self.assertIn("export_document", approval_names)
        self.assertIn("edit_file", approval_names)
        self.assertIn("run_command", approval_names)

    def test_task_planner_decomposition(self):
        planner = TaskPlanner()
        registry = ToolRegistry(auto_register_defaults=True)
        tools = registry.list_tools()

        plan = planner.create_plan("Calculate math using python code", available_tools=tools)
        self.assertGreater(len(plan.steps), 0)
        self.assertEqual(plan.goal, "Calculate math using python code")

    def test_ai_agent_engine_react_tool_execution_loop(self):
        registry = ToolRegistry(auto_register_defaults=False)
        registry.register_tool(CodeExecutionTool())

        agent = AIAgentEngine(
            tool_registry=registry,
            tool_executor=ToolExecutor(require_user_approval_callback=lambda name, params: True),
        )
        mock_provider = MagicMock()

        # Turn 1: LLM returns tool action
        res1 = ChatResponse(
            content="Thought: I need to calculate 21 * 2.\nAction: python_interpreter\nAction Input: print(21 * 2)",
            model="deepseek/deepseek-chat",
            provider_id="mock_provider",
        )
        # Turn 2: LLM processes observation and returns final answer
        res2 = ChatResponse(
            content="Final Answer: The result of 21 * 2 is 42.",
            model="deepseek/deepseek-chat",
            provider_id="mock_provider",
        )
        mock_provider.chat.side_effect = [res1, res2]
        agent.provider_manager = mock_provider

        output = agent.execute_task("Calculate 21 * 2", model="deepseek/deepseek-chat")
        self.assertIn("42", output)
        self.assertEqual(mock_provider.chat.call_count, 2)


if __name__ == "__main__":
    unittest.main()
