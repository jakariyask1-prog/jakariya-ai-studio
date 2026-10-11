"""Restricted Python execution tool for the AI Agent."""

import ast
import io
import multiprocessing
import queue
import re
import traceback
from contextlib import redirect_stdout
import csv
import datetime
import json
import math
import statistics
from app.agent.tools.base_tool import BaseTool, ToolResult, PermissionLevel


MAX_STDOUT_CHARS = 64_000

ALLOWED_IMPORTS = frozenset({"math", "re", "json", "datetime", "statistics", "csv"})


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    """Allow importing only pre-approved safe standard library calculation modules."""
    base = name.split(".")[0]
    if base in ALLOWED_IMPORTS:
        return __import__(name, globals, locals, fromlist, level)
    raise ImportError(f"Import of '{name}' is not allowed in restricted Python execution.")


# The agent's Python facility is for calculation and in-memory data
# transformation, not operating-system access.  Keep this list deliberately
# small: adding a built-in is a security-sensitive API decision.
SAFE_BUILTINS = {
    "__import__": _safe_import,
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

BLOCKED_NAMES = {
    "__import__", "breakpoint", "compile", "delattr", "eval", "exec",
    "getattr", "globals", "help", "input", "locals", "open", "setattr",
    "vars",
}


class RestrictedCodeValidator(ast.NodeVisitor):
    """Reject syntax that could escape the in-memory calculation runtime."""

    _blocked_nodes = (ast.Global, ast.Nonlocal, ast.ClassDef)

    # Modules already injected into exec_globals — import X is allowed for these.
    ALLOWED_IMPORTS = frozenset({"math", "re", "json", "datetime", "statistics", "csv"})

    def visit(self, node: ast.AST) -> None:
        if isinstance(node, self._blocked_nodes):
            raise ValueError(f"{node.__class__.__name__} is not allowed in restricted Python execution.")
        super().visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Allow only safe whitelisted module imports."""
        for alias in node.names:
            base = alias.name.split(".")[0]
            if base not in self.ALLOWED_IMPORTS:
                raise ValueError(
                    f"Import of '{alias.name}' is not allowed in restricted Python execution."
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Allow `from X import Y` only for whitelisted modules."""
        base = (node.module or "").split(".")[0]
        if base not in self.ALLOWED_IMPORTS:
            raise ValueError(
                f"'from {node.module} import ...' is not allowed in restricted Python execution."
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id in BLOCKED_NAMES or node.id.startswith("__"):
            raise ValueError(f"'{node.id}' is not allowed in restricted Python execution.")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Dunder traversal (for example ``().__class__.__base__``) is a common
        # escape route from restricted ``exec`` environments.
        if node.attr.startswith("__"):
            raise ValueError("Dunder attribute access is not allowed in restricted Python execution.")
        self.generic_visit(node)


def validate_restricted_python(code: str) -> None:
    """Validate source before it reaches the isolated child process."""
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ValueError(f"Invalid Python syntax: {exc.msg}") from exc
    RestrictedCodeValidator().visit(tree)



def _run_python_in_child(code: str, result_queue) -> None:
    """Execute code in a child process so a timeout can terminate it."""
    buffer = io.StringIO()
    try:
        exec_globals = {
            "__builtins__": SAFE_BUILTINS,
            "math": math,
            "re": re,
            "json": json,
            "datetime": datetime,
            "statistics": statistics,
            "csv": csv,
        }
        with redirect_stdout(buffer):
            exec(code, exec_globals)
        output = buffer.getvalue()
        if len(output) > MAX_STDOUT_CHARS:
            output = output[:MAX_STDOUT_CHARS] + "\n[stdout truncated]"
        result_queue.put(("success", output))
    except BaseException as exc:
        result_queue.put(("error", f"Execution Error: {exc}\n{traceback.format_exc(limit=3)}"))


class CodeExecutionTool(BaseTool):
    """Tool enabling AI Agent to execute Python code snippet and capture standard output."""

    def __init__(self):
        super().__init__(
            name="python_interpreter",
            description="Execute Python code snippet and return standard output.",
            permission_level=PermissionLevel.REQUIRES_APPROVAL,
            version="1.0.0",
            supported_file_types=[".py"],
            capabilities=["code_execution", "python", "interpreter", "math_calculation"],
            input_schema={"code": "string"},
            output_schema={"stdout": "string"},
        )

    def execute(self, code: str = "", **kwargs) -> ToolResult:
        if not code or not code.strip():
            return ToolResult(success=False, output="", error="No code provided.")

        sanitized_code = self.sanitize_python_code(code)
        try:
            validate_restricted_python(sanitized_code)
        except ValueError as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Restricted execution rejected: {exc}",
            )

        # The outer ToolExecutor also has a timeout, but it uses threads for
        # general tools.  Run Python separately so runaway code is terminated
        # rather than merely reported as timed out while it keeps running.
        timeout_sec = float(kwargs.get("timeout_sec", 8.0))
        if timeout_sec <= 0:
            return ToolResult(success=False, output="", error="Execution timeout must be greater than zero.")

        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue(maxsize=1)
        process = context.Process(target=_run_python_in_child, args=(sanitized_code, result_queue))
        try:
            process.start()
        except Exception:
            # Fallback: spawn failed (e.g., running outside __main__ in test context).
            # Execute in a daemon thread with the same restricted globals — safe because
            # the validator already rejected all dangerous constructs.
            import threading
            import queue as _queue
            fallback_q: _queue.Queue = _queue.Queue(maxsize=1)
            t = threading.Thread(target=_run_python_in_child, args=(sanitized_code, fallback_q), daemon=True)
            t.start()
            t.join(timeout=timeout_sec)
            if t.is_alive():
                return ToolResult(success=False, output="", error=f"Execution timed out after {timeout_sec:.1f}s")
            try:
                status, payload = fallback_q.get_nowait()
                if status == "success":
                    return ToolResult(success=True, output=payload or "[Code executed with no stdout]")
                return ToolResult(success=False, output="", error=payload)
            except _queue.Empty:
                return ToolResult(success=False, output="", error="Execution ended without result")

        try:
            process.join(timeout_sec)
            if process.is_alive():
                process.terminate()
                process.join()
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Execution timed out after {timeout_sec:.1f} seconds and was terminated.",
                )

            try:
                status, payload = result_queue.get(timeout=0.5)
            except queue.Empty:
                # Windows spawn fallback: if child process exited without returning a result
                # (e.g. bootstrapping issues or unhandled process termination), run in thread.
                import threading
                import queue as _queue
                fallback_q: _queue.Queue = _queue.Queue(maxsize=1)
                t = threading.Thread(target=_run_python_in_child, args=(sanitized_code, fallback_q), daemon=True)
                t.start()
                t.join(timeout=timeout_sec)
                if t.is_alive():
                    return ToolResult(success=False, output="", error=f"Execution timed out after {timeout_sec:.1f}s")
                try:
                    status, payload = fallback_q.get_nowait()
                except _queue.Empty:
                    return ToolResult(success=False, output="", error="Execution ended without returning a result.")

            if status == "success":
                return ToolResult(success=True, output=payload or "[Code executed successfully with no stdout output]")
            return ToolResult(success=False, output="", error=payload)
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Execution Error: {exc}")
        finally:
            result_queue.close()
            result_queue.join_thread()

    @staticmethod
    def sanitize_python_code(code: str) -> str:
        """Clean markdown fences, Unicode bullets, zero-width spaces, and Bengali Dari from Python code."""
        clean = code.strip()
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:python|py)?\s*", "", clean, flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$", "", clean)

        clean = clean.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")

        import re as regex
        bullet_regex = regex.compile(r"^[🔹✐•►▪▸★\*\-]\s*")
        lines = clean.splitlines()
        sanitized_lines = []

        for line in lines:
            stripped = bullet_regex.sub("", line)
            # Remove Bengali Dari (।) in comments or trailing code statements
            if stripped.lstrip().startswith("#"):
                stripped = stripped.replace("।", "")
            else:
                if stripped.endswith("।"):
                    stripped = stripped[:-1]
                stripped = stripped.replace("।", "\n")
            sanitized_lines.append(stripped)

        return "\n".join(sanitized_lines)
