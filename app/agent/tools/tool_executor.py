"""Dedicated Tool Executor with Validation, Cache, Timeout, Timing, and Structured Logging (Part 3, 4, 9)."""

import time
import logging
from typing import Any, Optional
from app.agent.tools.base_tool import BaseTool, ToolResult
from app.agent.tools.tool_cache import ToolCache
from app.agent.tools.timeout_manager import TimeoutManager

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Dedicated Tool Executor responsible for permission validation, input checking, caching, timeouts, timing, and exception handling."""

    def __init__(
        self,
        require_user_approval_callback: Optional[Any] = None,
        cache: Optional[ToolCache] = None,
        timeout_manager: Optional[TimeoutManager] = None,
    ):
        self.require_user_approval_callback = require_user_approval_callback
        self.cache = cache or ToolCache()
        self.timeout_manager = timeout_manager or TimeoutManager()

    def execute_tool(self, tool: BaseTool, **kwargs: Any) -> ToolResult:
        """Safely execute tool with validation, cache checking, operational timeouts, execution timing, and structured logging."""
        tool_name = tool.name
        start_time = time.perf_counter()

        logger.info("[ToolExecutor] Preparing execution for tool '%s' (params=%s)", tool_name, list(kwargs.keys()))

        # 1. Validate tool state
        if not getattr(tool, "enabled", True):
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            msg = f"Tool '{tool_name}' is currently disabled."
            logger.warning("[ToolExecutor] Execution rejected: %s", msg)
            return ToolResult(success=False, output="", error=msg, execution_time_ms=elapsed_ms)

        # 2. Check Tool Cache (Part 4)
        cached_result = self.cache.get(tool, **kwargs)
        if cached_result is not None:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            cached_result.execution_time_ms = round(elapsed_ms, 2)
            logger.info("[ToolExecutor] Served tool '%s' output from ToolCache (%.2fms)", tool_name, elapsed_ms)
            return cached_result

        # 3. Permission check (Part 1)
        if tool.requires_approval():
            logger.info("[ToolExecutor] Tool '%s' requires user approval (level=%s)", tool_name, tool.permission_level)
            if self.require_user_approval_callback is None:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                msg = f"Tool '{tool_name}' requires user approval, but no approval handler is configured."
                logger.error("[ToolExecutor] Execution rejected: %s", msg)
                return ToolResult(success=False, output="", error=msg, execution_time_ms=elapsed_ms)

            approved = self.require_user_approval_callback(tool_name, kwargs)
            if not approved:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                msg = f"Execution of tool '{tool_name}' was declined by user permission policy."
                logger.warning("[ToolExecutor] Execution declined: %s", msg)
                return ToolResult(success=False, output="", error=msg, execution_time_ms=elapsed_ms)

        # 4. Safe execution & Timeout & Timing capture (Part 3 & Part 9)
        timeout_sec = self.timeout_manager.get_tool_timeout(tool_name)
        try:
            result = self.timeout_manager.run_with_timeout(
                tool.execute,
                kwargs=kwargs,
                timeout_sec=timeout_sec,
                op_name=f"Tool '{tool_name}'",
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            result.execution_time_ms = round(elapsed_ms, 2)

            if result.success:
                logger.info("[ToolExecutor] Tool '%s' completed successfully in %.2fms", tool_name, result.execution_time_ms)
                # Store in cache if read-only
                self.cache.set(tool, kwargs, result)
            else:
                logger.warning("[ToolExecutor] Tool '%s' failed in %.2fms: %s", tool_name, result.execution_time_ms, result.error)

            return result
        except TimeoutError as te:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = str(te)
            logger.error("[ToolExecutor] Timeout in '%s': %s (took %.2fms)", tool_name, err_msg, elapsed_ms)
            return ToolResult(
                success=False,
                output="",
                error=err_msg,
                execution_time_ms=round(elapsed_ms, 2),
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            err_msg = f"Unhandled Exception in '{tool_name}': {exc}"
            logger.error("[ToolExecutor] %s (took %.2fms)", err_msg, elapsed_ms, exc_info=True)
            return ToolResult(
                success=False,
                output="",
                error=err_msg,
                execution_time_ms=round(elapsed_ms, 2),
            )
