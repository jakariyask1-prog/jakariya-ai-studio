"""Tests for Agent Loop Guardrails, Error Observation Tracebacks, and Rate Limit Caps."""

import unittest
from unittest.mock import MagicMock, patch
from app.agent.agent_engine import AIAgentEngine
from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel
from app.agent.tool_registry import ToolRegistry
from app.providers.models.chat_request import ChatRequest
from app.providers.models.chat_response import ChatResponse
from app.providers.implementations.groq_provider import GroqProvider


class FailingTestTool(BaseTool):
    def __init__(self, name="failing_cmd"):
        super().__init__(
            name=name,
            description="Tool that simulates command/test failure",
            permission_level=PermissionLevel.READ_ONLY,
        )

    def execute(self, **kwargs) -> ToolResult:
        return ToolResult(
            success=False,
            output="Traceback (most recent call last):\n  File 'test.py', line 10, in test_fail\nAssertionError: Expected 200 but got 500",
            error="Command exited with code 1",
            execution_time_ms=45.0,
        )


class TestAgentLoopGuardrails(unittest.TestCase):
    def setUp(self):
        self.engine = AIAgentEngine()

    def test_tool_failure_observation_includes_traceback(self):
        """Verify that when a tool fails, res.output (traceback) is not discarded."""
        registry = ToolRegistry()
        fail_tool = FailingTestTool()
        registry.register_tool(fail_tool)
        engine = AIAgentEngine(tool_registry=registry)

        # Mock provider responses: 1) call failing tool, 2) give final answer
        mock_provider = MagicMock()
        mock_provider.chat.side_effect = [
            ChatResponse(
                content="Thought: Run the test\nAction: failing_cmd\nAction Input: test.py",
                model="test-model",
                provider_id="test-provider",
            ),
            ChatResponse(
                content="Final Answer: The test failed with AssertionError.",
                model="test-model",
                provider_id="test-provider",
            ),
        ]
        engine.provider_manager = mock_provider

        output = engine.execute_task("Run tests on backend")
        self.assertIn("Final Answer:", output)

        # Inspect messages sent in second turn to ensure traceback was in the observation
        second_call_messages = mock_provider.chat.call_args_list[1][0][0].messages
        obs_content = "".join(str(getattr(m, "content", "")) for m in second_call_messages)
        self.assertIn("AssertionError: Expected 200 but got 500", obs_content)
        self.assertIn("Command exited with code 1", obs_content)

    def test_consecutive_tool_failures_inject_directive(self):
        """Verify that repeating failures inject [SYSTEM DIRECTIVE]."""
        registry = ToolRegistry()
        fail_tool = FailingTestTool()
        registry.register_tool(fail_tool)
        engine = AIAgentEngine(tool_registry=registry)

        mock_provider = MagicMock()
        mock_provider.chat.side_effect = [
            ChatResponse(
                content="Thought: Attempt 1\nAction: failing_cmd\nAction Input: test1",
                model="test-model",
                provider_id="test-provider",
            ),
            ChatResponse(
                content="Thought: Attempt 2\nAction: failing_cmd\nAction Input: test2",
                model="test-model",
                provider_id="test-provider",
            ),
            ChatResponse(
                content="Final Answer: Concluding after repeated failures.",
                model="test-model",
                provider_id="test-provider",
            ),
        ]
        engine.provider_manager = mock_provider

        output = engine.execute_task("Run backend tests")
        self.assertIn("Final Answer:", output)

        # The observation after 2nd failure must contain the consecutive failure directive
        third_call_messages = mock_provider.chat.call_args_list[2][0][0].messages
        obs_content = "".join(str(getattr(m, "content", "")) for m in third_call_messages)
        self.assertIn("Tools have failed 2 consecutive times", obs_content)

    def test_identical_failing_tool_call_injects_critical_warning(self):
        """Verify that repeating the exact same failing tool call injects critical warning."""
        registry = ToolRegistry()
        fail_tool = FailingTestTool()
        registry.register_tool(fail_tool)
        engine = AIAgentEngine(tool_registry=registry)

        mock_provider = MagicMock()
        mock_provider.chat.side_effect = [
            ChatResponse(
                content="Thought: Attempt 1\nAction: failing_cmd\nAction Input: identical_input",
                model="test-model",
                provider_id="test-provider",
            ),
            ChatResponse(
                content="Thought: Attempt 2\nAction: failing_cmd\nAction Input: identical_input",
                model="test-model",
                provider_id="test-provider",
            ),
            ChatResponse(
                content="Final Answer: Fixed and completed.",
                model="test-model",
                provider_id="test-provider",
            ),
        ]
        engine.provider_manager = mock_provider

        output = engine.execute_task("Run backend tests")
        self.assertIn("Final Answer:", output)

        third_call_messages = mock_provider.chat.call_args_list[2][0][0].messages
        obs_content = "".join(str(getattr(m, "content", "")) for m in third_call_messages)
        self.assertIn("You repeated the exact same tool call that already failed", obs_content)

    def test_parse_tool_call_edit_file_key_value(self):
        """Verify non-JSON key-value parsing for edit_file."""
        text = (
            "Action: edit_file\n"
            "Action Input:\n"
            "file_path: backend.py\n"
            "target_content: def old_fn():\n"
            "    return 1\n"
            "replacement_content: def new_fn():\n"
            "    return 2\n"
            "allow_multiple: false"
        )
        parsed = self.engine._parse_tool_call(text)
        self.assertIsNotNone(parsed)
        tool_name, params = parsed
        self.assertEqual(tool_name, "edit_file")
        self.assertEqual(params.get("file_path"), "backend.py")
        self.assertEqual(params.get("target_content"), "def old_fn():\n    return 1")
        self.assertEqual(params.get("replacement_content"), "def new_fn():\n    return 2")
        self.assertFalse(params.get("allow_multiple"))

    def test_parse_tool_call_run_command_prefix_stripping(self):
        """Verify run_command strips 'command:' prefix if LLM generates it in plain text."""
        text = "Action: run_command\nAction Input: command: pytest tests/test_backend.py"
        parsed = self.engine._parse_tool_call(text)
        self.assertIsNotNone(parsed)
        tool_name, params = parsed
        self.assertEqual(tool_name, "run_command")
        self.assertEqual(params.get("command"), "pytest tests/test_backend.py")

    def test_groq_provider_caps_max_tokens_to_1000(self):
        """Verify GroqProvider caps max_tokens to 1000 by default to respect free-tier TPM quota."""
        provider = GroqProvider(api_key="gsk_mock_valid_key_1234567")
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Groq response"
        mock_choice.message.reasoning_content = None
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice], usage=None
        )
        provider._client = mock_client
        provider._last_key = provider.api_key
        provider._last_url = provider.base_url

        # Unconstrained request (max_tokens=None)
        req = ChatRequest(messages=[], model="qwen/qwen3.8-27b", max_tokens=None)
        provider.chat(req)
        kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(kwargs.get("max_tokens"), 1000)

        # High max_tokens request (max_tokens=4096)
        req2 = ChatRequest(messages=[], model="qwen/qwen3.8-27b", max_tokens=4096)
        provider.chat(req2)
        kwargs2 = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(kwargs2.get("max_tokens"), 1000)


if __name__ == "__main__":
    unittest.main()
