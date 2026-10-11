"""Central Tool Registry & Dynamic Tool Discovery Engine for AI Agent (Part 1 & Part 2)."""

import logging
from typing import Dict, List, Optional
from app.agent.tools.base_tool import BaseTool, PermissionLevel, ToolMetadata
from app.agent.tools.file_tool import FileReadTool, FileWriteTool
from app.agent.tools.directory_list_tool import DirectoryListTool
from app.agent.tools.file_search_tool import FileSearchTool
from app.agent.tools.file_edit_tool import FileEditTool
from app.agent.tools.terminal_tool import TerminalCommandTool
from app.agent.tools.code_execution_tool import CodeExecutionTool
from app.agent.tools.web_search_tool import WebSearchTool
from app.agent.tools.document_exporter_tool import DocumentExporterTool
from app.agent.tools.code_outline_tool import CodeOutlineTool
from app.agent.tools.diagnostics_tool import DiagnosticsTool
from app.agent.tools.git_tool import GitTool

logger = logging.getLogger(__name__)


TOOL_ALIASES: Dict[str, str] = {
    # File reading (Antigravity, Cursor, Claude Code)
    "view_file": "read_file",
    "view": "read_file",
    "cat": "read_file",
    "get_file": "read_file",
    "read": "read_file",
    # File writing
    "write": "write_file",
    "create_file": "write_file",
    "save_file": "write_file",
    # File editing (Antigravity, Cursor, Claude Code)
    "replace_file_content": "edit_file",
    "replace_content": "edit_file",
    "patch_file": "edit_file",
    "edit": "edit_file",
    "modify_file": "edit_file",
    "str_replace": "edit_file",
    # Directory listing
    "list_dir": "list_directory",
    "browse_folder": "list_directory",
    "ls": "list_directory",
    "dir": "list_directory",
    "tree": "list_directory",
    "glob": "list_directory",
    # Code / file search
    "grep": "search_files",
    "find_in_files": "search_files",
    "search": "search_files",
    "search_file": "search_files",
    # Terminal / shell
    "terminal": "run_command",
    "execute_command": "run_command",
    "shell": "run_command",
    "bash": "run_command",
    "powershell": "run_command",
    "cmd": "run_command",
    # Diagnostics & Linting
    "diagnostics": "check_diagnostics",
    "lint_file": "check_diagnostics",
    "lint": "check_diagnostics",
    "syntax_check": "check_diagnostics",
    # Code Outline & Symbols
    "outline": "code_outline",
    "symbol_search": "code_outline",
    "symbols": "code_outline",
    # Git
    "git": "git_tool",
    "git_status": "git_tool",
    "git_diff": "git_tool",
    # Document export
    "export": "export_document",
    "save_document": "export_document",
    # Python
    "python": "python_interpreter",
    "py": "python_interpreter",
    "exec_python": "python_interpreter",
}


class ToolRegistry:
    """Registry maintaining available tools, capabilities, enabled states, and dynamic tool discovery."""

    def __init__(self, auto_register_defaults: bool = True):
        self._tools: Dict[str, BaseTool] = {}
        if auto_register_defaults:
            self.auto_register_default_tools()

    def auto_register_default_tools(self) -> None:
        """Automatically register the core AI Agent tools."""
        self.register_tool(FileReadTool())
        self.register_tool(FileWriteTool())
        self.register_tool(DirectoryListTool())
        self.register_tool(FileSearchTool())
        self.register_tool(FileEditTool())
        self.register_tool(TerminalCommandTool())
        self.register_tool(CodeExecutionTool())
        self.register_tool(WebSearchTool())
        self.register_tool(DocumentExporterTool())
        self.register_tool(CodeOutlineTool())
        self.register_tool(DiagnosticsTool())
        self.register_tool(GitTool())

    def register_tool(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        logger.info("[ToolRegistry] Registered tool '%s' (v%s, permission=%s)", tool.name, tool.metadata.version, tool.permission_level)

    def enable_tool(self, name: str) -> bool:
        """Enable tool execution by name."""
        tool = self.get_tool(name)
        if tool:
            tool.enabled = True
            logger.info("[ToolRegistry] Tool '%s' enabled", name)
            return True
        return False

    def disable_tool(self, name: str) -> bool:
        """Disable tool execution by name."""
        tool = self.get_tool(name)
        if tool:
            tool.enabled = False
            logger.info("[ToolRegistry] Tool '%s' disabled", name)
            return True
        return False

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get tool instance by name or alias."""
        if not name:
            return None
        tool = self._tools.get(name)
        if tool:
            return tool
        canonical = TOOL_ALIASES.get(name.lower().strip())
        if canonical:
            return self._tools.get(canonical)
        return None

    def lookup_by_capability(self, capability: str) -> List[BaseTool]:
        """Find enabled tools that support a specific capability."""
        cap_clean = capability.lower().strip()
        matching = []
        for tool in self._tools.values():
            if tool.enabled and any(cap_clean in c.lower() for c in tool.metadata.capabilities):
                matching.append(tool)
        return matching

    def list_tools(
        self,
        permission_filter: Optional[PermissionLevel] = None,
        enabled_only: bool = True,
    ) -> List[BaseTool]:
        """Return list of registered tools, optionally filtered by status or permission level."""
        result = []
        for tool in self._tools.values():
            if enabled_only and not tool.enabled:
                continue
            if permission_filter and tool.permission_level != permission_filter:
                continue
            result.append(tool)
        return result

    def get_tool_metadata(self, name: str) -> Optional[ToolMetadata]:
        """Return full metadata schema for a given tool name."""
        tool = self.get_tool(name)
        return tool.metadata if tool else None

    def discover_best_tool(self, query_or_capability: str) -> Optional[BaseTool]:
        """Part 2 Tool Discovery: Dynamically select the best tool matching query or capability without hardcoding."""
        clean = query_or_capability.lower().strip()
        if not clean:
            return None

        # 1. Capability exact or partial match
        matching = self.lookup_by_capability(clean)
        if matching:
            return matching[0]

        # 2. Keyword heuristic matching against tool description and name
        best_tool = None
        highest_score = 0
        for tool in self.list_tools(enabled_only=True):
            score = 0
            if tool.name.lower() in clean or clean in tool.name.lower():
                score += 3
            for word in clean.split():
                if word in tool.description.lower():
                    score += 1
            if score > highest_score:
                highest_score = score
                best_tool = tool

        if best_tool:
            logger.info("[ToolDiscovery] Discovered best tool '%s' for query '%s'", best_tool.name, query_or_capability)
            return best_tool

        return None
