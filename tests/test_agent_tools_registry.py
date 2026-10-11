"""Unit tests for Tool Metadata, Registry, and Dynamic Discovery (Parts 1, 2, 8)."""

import unittest
from app.agent.tools.base_tool import PermissionLevel
from app.agent.tools.file_tool import FileReadTool, FileWriteTool
from app.agent.tools.code_execution_tool import CodeExecutionTool
from app.agent.tools.web_search_tool import WebSearchTool
from app.agent.tool_registry import ToolRegistry


class TestAgentToolsRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry(auto_register_defaults=True)

    def test_tool_metadata_attributes(self):
        read_tool = self.registry.get_tool("read_file")
        self.assertIsNotNone(read_tool)
        meta = read_tool.metadata
        self.assertEqual(meta.name, "read_file")
        self.assertEqual(meta.version, "1.0.0")
        self.assertEqual(meta.permission, PermissionLevel.REQUIRES_APPROVAL)
        self.assertIn(".txt", meta.supported_file_types)
        self.assertIn("file_io", meta.capabilities)
        self.assertIn("file_path", meta.input_schema)

    def test_enable_disable_tools(self):
        self.assertTrue(self.registry.disable_tool("python_interpreter"))
        tools = self.registry.list_tools(enabled_only=True)
        tool_names = [t.name for t in tools]
        self.assertNotIn("python_interpreter", tool_names)

        self.assertTrue(self.registry.enable_tool("python_interpreter"))
        tools_after = self.registry.list_tools(enabled_only=True)
        self.assertIn("python_interpreter", [t.name for t in tools_after])

    def test_lookup_by_capability(self):
        math_tools = self.registry.lookup_by_capability("python")
        self.assertEqual(len(math_tools), 1)
        self.assertEqual(math_tools[0].name, "python_interpreter")

        search_tools = self.registry.lookup_by_capability("web_search")
        self.assertEqual(len(search_tools), 1)
        self.assertEqual(search_tools[0].name, "web_search")

    def test_dynamic_tool_discovery(self):
        # Discover by capability
        discovered_code = self.registry.discover_best_tool("math_calculation")
        self.assertIsNotNone(discovered_code)
        self.assertEqual(discovered_code.name, "python_interpreter")

        # Discover by description keyword
        discovered_search = self.registry.discover_best_tool("Find live news and facts")
        self.assertIsNotNone(discovered_search)
        self.assertEqual(discovered_search.name, "web_search")


if __name__ == "__main__":
    unittest.main()
