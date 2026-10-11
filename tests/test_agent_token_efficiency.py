"""Test suite for AI Agent Engine Token Efficiency & Fast Execution (Turn 1 Exits, No Code Hijacking, Observation Pruning)."""

import unittest
from pathlib import Path
from unittest.mock import MagicMock
from app.agent.agent_engine import AIAgentEngine
from app.agent.context.context_manager import AgentContextManager
from app.agent.tools.base_tool import BaseTool, PermissionLevel, ToolResult
from app.agent.tool_registry import ToolRegistry
from app.agent.tools.tool_executor import ToolExecutor
from app.providers.models.chat_response import ChatResponse


class DummyReadOnlyTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="dummy_reader",
            description="Safe read-only test tool",
            permission_level=PermissionLevel.READ_ONLY,
        )
        self.call_count = 0

    def execute(self, **kwargs) -> ToolResult:
        self.call_count += 1
        return ToolResult(success=True, output=f"dummy result {self.call_count}")


class TestAgentTokenEfficiency(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(auto_register_defaults=False)
        self.dummy_tool = DummyReadOnlyTool()
        self.registry.register_tool(self.dummy_tool)

    def test_conversational_question_exits_in_one_turn_without_nudging(self):
        """Conversational or explanatory questions must exit in 1 turn without token-wasting nudges."""
        engine = AIAgentEngine(tool_registry=self.registry)
        mock_provider = MagicMock()
        mock_provider.chat.return_value = ChatResponse(
            content="Python is a high-level interpreted programming language created by Guido van Rossum.",
            model="mock-model",
            provider_id="mock",
        )
        engine.provider_manager = mock_provider

        output = engine.execute_task("What is Python and how does it work?", model="mock-model")

        self.assertIn("Python is a high-level", output)
        # MUST complete in exactly 1 call (Turn 0) — no 2nd turn nudge!
        self.assertEqual(mock_provider.chat.call_count, 1)

    def test_explanation_with_python_code_block_not_hijacked_as_tool_execution(self):
        """When an LLM provides a python code snippet in markdown, it must NOT be executed as python_interpreter."""
        engine = AIAgentEngine(tool_registry=self.registry)
        mock_provider = MagicMock()
        code_response = (
            "Here is how you reverse a list in Python:\n"
            "```python\n"
            "numbers = [1, 2, 3, 4, 5]\n"
            "reversed_numbers = numbers[::-1]\n"
            "print(reversed_numbers)\n"
            "```\n"
            "This uses slice notation."
        )
        mock_provider.chat.return_value = ChatResponse(
            content=code_response,
            model="mock-model",
            provider_id="mock",
        )
        engine.provider_manager = mock_provider

        output = engine.execute_task("How do I reverse a list in Python?", model="mock-model")

        self.assertIn("Here is how you reverse a list", output)
        self.assertIn("```python", output)
        # Exactly 1 call — must NOT trigger python_interpreter or extra turns!
        self.assertEqual(mock_provider.chat.call_count, 1)

    def test_explicit_action_triggers_nudge_only_when_demanded(self):
        """When user explicitly orders 'save to desktop', nudge is triggered only if tool was omitted."""
        engine = AIAgentEngine(tool_registry=self.registry)
        self.assertTrue(engine._requires_tools("Save to desktop a file named test.txt"))
        self.assertTrue(engine._requires_tools("Search the web for latest AI news"))
        self.assertTrue(engine._requires_tools("Run command pytest tests"))
        # Pure questions do NOT require tools
        self.assertFalse(engine._requires_tools("What is Python?"))
        self.assertFalse(engine._requires_tools("How to reverse a string?"))
        self.assertFalse(engine._requires_tools("Explain git rebase vs merge"))
        self.assertFalse(engine._requires_tools("Python এ কিভাবে ফাংশন লিখতে হয়?"))

    def test_context_observation_pruning_conserves_tokens(self):
        """Older tool observations (> 2 turns ago) have their bulky data pruned, saving prompt tokens."""
        ctx = AgentContextManager()
        # Add 3 large tool observations
        large_output_1 = "Line A " * 1000  # ~7,000 chars
        large_output_2 = "Line B " * 1000  # ~7,000 chars
        large_output_3 = "Line C " * 1000  # ~7,000 chars

        ctx.add_tool_observation("tool_1", large_output_1)
        ctx.add_assistant_message("Thought: step 1 done")
        ctx.add_tool_observation("tool_2", large_output_2)
        ctx.add_assistant_message("Thought: step 2 done")
        ctx.add_tool_observation("tool_3", large_output_3)

        history = ctx.get_formatted_history()
        self.assertEqual(len(history), 5)

        # Observation 1 (oldest) should be pruned
        obs_1_content = history[0].content
        self.assertIn("[... Older tool output pruned to save tokens", obs_1_content)
        self.assertLess(len(obs_1_content), 2000)

        # Observation 2 and 3 (most recent 2) must remain full
        obs_2_content = history[2].content
        obs_3_content = history[4].content
        self.assertNotIn("[... Older tool output pruned to save tokens", obs_2_content)
        self.assertNotIn("[... Older tool output pruned to save tokens", obs_3_content)
        self.assertGreater(len(obs_2_content), 5000)
        self.assertGreater(len(obs_3_content), 5000)

    def test_tool_cache_skips_redundant_read_executions(self):
        """Read-only tool results are cached within the turn loop to eliminate redundant operations."""
        executor = ToolExecutor(require_user_approval_callback=lambda n, p: True)
        engine = AIAgentEngine(tool_registry=self.registry, tool_executor=executor)
        mock_provider = MagicMock()

        # Turn 1: calls dummy_reader
        res1 = ChatResponse(
            content="Thought: Inspect reader.\nAction: dummy_reader\nAction Input: {}",
            model="mock",
            provider_id="mock",
        )
        # Turn 2: calls dummy_reader again with same params
        res2 = ChatResponse(
            content="Thought: Inspect reader again.\nAction: dummy_reader\nAction Input: {}",
            model="mock",
            provider_id="mock",
        )
        # Turn 3: Final Answer
        res3 = ChatResponse(
            content="Final Answer: Done reading.",
            model="mock",
            provider_id="mock",
        )
        mock_provider.chat.side_effect = [res1, res2, res3]
        engine.provider_manager = mock_provider

        output = engine.execute_task("Read test data", model="mock")
        self.assertIn("Done reading", output)
        # The dummy_tool should only have been physically executed ONCE; the second was a cache hit!
        self.assertEqual(self.dummy_tool.call_count, 1)

    def test_anti_cop_out_nudges_model_when_claiming_no_code_files_for_web_project(self):
        """Engine must reject false cop-outs claiming 'no source code' when .html files exist."""
        from app.agent.tools.directory_list_tool import DirectoryListTool
        self.registry.register_tool(DirectoryListTool())
        engine = AIAgentEngine(tool_registry=self.registry)
        mock_provider = MagicMock()

        # Turn 1: Model calls list_directory
        res1 = ChatResponse(
            content="Thought: List files.\nAction: list_directory\nAction Input: my_project",
            model="mock",
            provider_id="mock",
        )
        # Turn 2: Model tries to cop out saying there are no source-code files
        res2 = ChatResponse(
            content="Final Answer: Explored folder and found index.html. There are no source-code files in this directory.",
            model="mock",
            provider_id="mock",
        )
        # Turn 3: After nudge, model inspects and provides proper final answer
        res3 = ChatResponse(
            content="Final Answer: Successfully inspected index.html and verified valid HTML5 structure.",
            model="mock",
            provider_id="mock",
        )
        mock_provider.chat.side_effect = [res1, res2, res3]
        engine.provider_manager = mock_provider

        # Mock DirectoryListTool to return index.html
        with unittest.mock.patch.object(
            DirectoryListTool,
            "execute",
            return_value=ToolResult(success=True, output="1. index.html\n2. style.css\n3. image.jpg"),
        ):
            output = engine.execute_task("এই প্রজেক্টের ফাইলগুলো স্ক্যান করো এবং কোডে কোনো ভুল বা বাগ থাকলে তা ফিক্স করো", model="mock")

        self.assertIn("Successfully inspected index.html", output)
        # Call count must be 3 because turn 2 cop-out was intercepted and nudged!
        self.assertEqual(mock_provider.chat.call_count, 3)

    def test_diagnostics_html_validation(self):
        """DiagnosticsTool must validate HTML structure and report unclosed tags."""
        import tempfile
        from app.agent.tools.diagnostics_tool import DiagnosticsTool
        diag = DiagnosticsTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Clean HTML
            clean_html = Path(tmpdir) / "clean.html"
            clean_html.write_text("<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Hello</h1></body></html>", encoding="utf-8")
            res_clean = diag.execute(file_path=str(clean_html))
            self.assertTrue(res_clean.success)
            self.assertIn("HTML & Web Diagnostics Passed", res_clean.output)

            # 2. Mismatched tag HTML
            bad_html = Path(tmpdir) / "bad.html"
            bad_html.write_text("<div><p>Hello</div></p>", encoding="utf-8")
            res_bad = diag.execute(file_path=str(bad_html))
            self.assertFalse(res_bad.success)
            self.assertIn("Mismatched HTML tag", res_bad.error)

    def test_code_outline_html_parsing(self):
        """CodeOutlineTool must outline landmarks and script functions in HTML."""
        import tempfile
        from app.agent.tools.code_outline_tool import CodeOutlineTool
        outline = CodeOutlineTool()

        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "index.html"
            html_file.write_text(
                "<!DOCTYPE html><html><head><title>My Portfolio</title></head>"
                "<body><nav>Nav</nav><section id='projects'>Projects</section>"
                "<script>function startApp() {}</script></body></html>",
                encoding="utf-8"
            )
            res = outline.execute(file_path=str(html_file))
            self.assertTrue(res.success)
            self.assertIn("My Portfolio", res.output)
            self.assertIn("<section id=\"projects\">", res.output)
            self.assertIn("startApp()", res.output)


if __name__ == "__main__":
    unittest.main()
