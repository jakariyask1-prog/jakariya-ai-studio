"""Background Qt Worker & Controller for AIAgentEngine asynchronous execution."""

from __future__ import annotations

import threading
import uuid
import logging
import hashlib
import json
from typing import Any, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from app.agent.agent_engine import AIAgentEngine

logger = logging.getLogger(__name__)

# Module-level thread-safe approval registry.
# Keyed by approval_id (str UUID). Value: {"event": threading.Event, "result": [bool]}
# This avoids passing mutable Python objects through Qt's QueuedConnection which copies them.
_approval_registry: dict[str, dict] = {}
_registry_lock = threading.Lock()
# File creation and code execution are deliberately protected by explicit
# approval. Five minutes gives users enough time to inspect a long document
# request without turning the approval into an unexpected rejection.
APPROVAL_TIMEOUT_SECONDS = 300


class AgentWorker(QObject):
    """Background worker executing AIAgentEngine tasks off the main UI thread."""

    started  = Signal()
    progress = Signal(str, str, bool)   # (message, tool_name, is_tool_running)
    finished = Signal(str)
    failed   = Signal(str)

    # Only primitive types are passed through the queued signal.
    # approval_id is a UUID string used to look up event/result in _approval_registry.
    request_approval = Signal(str, str)  # (tool_name, approval_id)

    def __init__(self, agent_engine: Optional[AIAgentEngine] = None):
        super().__init__()
        self.agent_engine = agent_engine or AIAgentEngine()
        self.agent_engine.set_approval_callback(self._ask_user_approval)
        self._approved_actions: set[str] = set()
        self._auto_approve_task: bool = False
        self._approval_lock = threading.Lock()

    def enable_auto_approval_for_task(self) -> None:
        """Allow all subsequent tool executions in the active task without prompting."""
        with self._approval_lock:
            self._auto_approve_task = True
        logger.info("[AgentWorker] Task-wide auto-approval enabled.")

    # ------------------------------------------------------------------
    # Permission approval — always via signal+registry, never direct call
    # ------------------------------------------------------------------

    @staticmethod
    def _approval_fingerprint(tool_name: str, params: dict) -> str:
        """Bind remembered consent to one exact tool invocation, not a tool class."""
        payload = json.dumps(
            {"tool_name": tool_name, "params": params},
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _ask_user_approval(self, tool_name: str, params: dict) -> bool:
        """Request user approval from main GUI thread via signal+registry pattern."""
        with self._approval_lock:
            if self._auto_approve_task:
                logger.info("[AgentWorker] Tool '%s' auto-approved (task-wide auto-approval active).", tool_name)
                return True

            fingerprint = self._approval_fingerprint(tool_name, params)
            if fingerprint in self._approved_actions:
                logger.info("[AgentWorker] Exact action for tool '%s' already approved in this task.", tool_name)
                return True

        logger.info("[AgentWorker] Tool '%s' requesting user approval...", tool_name)

        approval_id = str(uuid.uuid4())
        event = threading.Event()
        entry = {
            "event": event,
            "result": [False],
            "params": params,
            "remember_for_task": False,
            "allow_all_for_task": False,
        }

        with _registry_lock:
            _approval_registry[approval_id] = entry

        # Emit signal with only primitive types — safe across threads
        self.request_approval.emit(tool_name, approval_id)

        # Block worker thread (NOT the main thread) until main thread resolves the dialog
        got_response = event.wait(timeout=APPROVAL_TIMEOUT_SECONDS)

        with _registry_lock:
            _approval_registry.pop(approval_id, None)

        if not got_response:
            logger.warning(
                "[AgentWorker] Approval timed out after %ss for tool '%s'",
                APPROVAL_TIMEOUT_SECONDS,
                tool_name,
            )
            return False

        approved = entry["result"][0]
        if approved:
            with self._approval_lock:
                if entry.get("allow_all_for_task"):
                    self._auto_approve_task = True
                    logger.info("[AgentWorker] Task-wide auto-approval activated for tool '%s' and subsequent actions.", tool_name)
                elif entry.get("remember_for_task"):
                    self._approved_actions.add(fingerprint)
                    logger.info("[AgentWorker] Exact action for tool '%s' approved for this task.", tool_name)
        logger.info("[AgentWorker] Tool '%s' approval result: %s", tool_name, approved)
        return approved

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    @Slot(object, str, str, list, int)
    def process_task(self, task_description: object, model: str, provider_id: str, history_msgs: list, max_turns: int = 15):
        """Execute the agent task and emit real-time progress updates."""
        # Consent never crosses task boundaries, even when the worker lives for
        # the whole application session.
        with self._approval_lock:
            self._approved_actions.clear()
            self._auto_approve_task = False
        self.started.emit()

        def on_agent_progress(p):
            msg = getattr(p, "message", str(p))
            tool_name = ""
            is_tool = False
            if "Action:" in msg or "Tool:" in msg or "Executing" in msg:
                is_tool = True
                if ":" in msg:
                    parts = msg.split(":", 1)[1].strip().split()
                    tool_name = parts[0] if parts else ""
            elif "Thought:" in msg:
                is_tool = False
            self.progress.emit(msg, tool_name, is_tool)

        try:
            output = self.agent_engine.execute_task(
                task_description=task_description,
                model=model,
                max_turns=max_turns,
                history=history_msgs,
                progress_callback=on_agent_progress,
                provider_id=provider_id or None,
            )
            # Guard: if agent returned empty, emit a meaningful fallback
            if not output or not output.strip():
                output = "Final Answer: Task completed. No output was generated by the agent."
            self.finished.emit(output)
        except Exception as exc:
            logger.error("[AgentWorker] Task failed: %s", exc, exc_info=True)
            self.failed.emit(str(exc))



class AgentController(QObject):
    """Manages thread lifecycle for AgentWorker execution."""

    started          = Signal()
    progress         = Signal(str, str, bool)
    finished         = Signal(str)
    failed           = Signal(str)
    request_approval = Signal(str, str)  # (tool_name, approval_id)

    dispatch_task = Signal(object, str, str, list, int)  # (task, model, provider, history, max_turns)

    def __init__(self):
        super().__init__()
        self.worker_thread = QThread()
        self.worker = AgentWorker()
        self.worker.moveToThread(self.worker_thread)

        self.dispatch_task.connect(self.worker.process_task)
        self.worker.started.connect(self.started)
        self.worker.progress.connect(self.progress)
        self.worker.finished.connect(self.finished)
        self.worker.failed.connect(self.failed)
        self.worker.request_approval.connect(self.request_approval)

        self.worker_thread.start()

    def run_agent_task(
        self,
        task_description: str | list[dict[str, Any]],
        model: str,
        provider_id: str,
        history_msgs: list,
        max_turns: int = 15,
    ) -> None:
        """Dispatch task execution to background worker thread."""
        self.dispatch_task.emit(task_description, model, provider_id, history_msgs, max_turns)

    def cancel_agent_task(self):
        """Cancel current task execution and unblock pending tool approvals."""
        if hasattr(self.worker, "agent_engine") and self.worker.agent_engine:
            self.worker.agent_engine.cancel()
        with _registry_lock:
            for entry in _approval_registry.values():
                entry["result"] = [False]
                entry["event"].set()

    def shutdown(self):
        """Stop worker thread safely."""
        if self.worker_thread and self.worker_thread.isRunning():
            self.worker_thread.quit()
            if not self.worker_thread.wait(2000):
                self.worker_thread.terminate()
                self.worker_thread.wait()
