"""Timeout Manager for Tool Execution & Agent Operations (Part 3)."""

import time
import logging
import concurrent.futures
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class TimeoutManager:
    """Configurable Timeout Manager for planning, tool execution, and python interpret steps."""

    def __init__(
        self,
        planning_timeout_sec: float = 15.0,
        tool_timeout_sec: float = 30.0,
        web_search_timeout_sec: float = 15.0,
        python_exec_timeout_sec: float = 10.0,
    ):
        self.planning_timeout_sec = planning_timeout_sec
        self.tool_timeout_sec = tool_timeout_sec
        self.web_search_timeout_sec = web_search_timeout_sec
        self.python_exec_timeout_sec = python_exec_timeout_sec

    def get_tool_timeout(self, tool_name: str) -> float:
        """Return specific timeout per tool type."""
        if tool_name == "web_search":
            return self.web_search_timeout_sec
        elif tool_name == "python_interpreter":
            return self.python_exec_timeout_sec
        return self.tool_timeout_sec

    def run_with_timeout(
        self,
        func: Callable[..., Any],
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        timeout_sec: Optional[float] = None,
        op_name: str = "Operation",
    ) -> Any:
        """Execute a function within a responsive timeout bound.

        Python threads cannot be forcefully stopped.  Callers that execute
        untrusted or side-effecting code must enforce their own hard timeout
        in a separate process.  This helper nevertheless returns promptly
        when its deadline is reached instead of blocking on executor cleanup.
        """
        limit = timeout_sec or self.tool_timeout_sec
        kwargs = kwargs or {}

        start_time = time.perf_counter()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(func, *args, **kwargs)
        try:
            result = future.result(timeout=limit)
        except concurrent.futures.TimeoutError:
            # ``cancel`` only succeeds before the thread begins running.  Do
            # not wait for shutdown here: doing so would negate the timeout.
            future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            msg = f"{op_name} timed out after {limit:.1f} seconds."
            logger.error("[TimeoutManager] %s (elapsed: %.2fms)", msg, elapsed_ms)
            raise TimeoutError(msg)
        except Exception:
            executor.shutdown(wait=True, cancel_futures=True)
            raise
        else:
            executor.shutdown(wait=True, cancel_futures=True)
            return result
