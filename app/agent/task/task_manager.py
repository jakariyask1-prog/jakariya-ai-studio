"""Task Manager with Retry Engine & Progress Tracking (Part 5, 6, 7)."""

import time
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional
from app.agent.planner.task_planner import TaskPlan
from app.agent.task.task_state import TaskState

logger = logging.getLogger(__name__)


@dataclass
class TaskProgress:
    """Snapshot of current task execution progress."""

    current_step: int
    total_steps: int
    percentage: float
    state: TaskState
    message: str


class TaskManager:
    """Manages task execution workflow states, progress tracking, and exponential backoff retries."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_sec: float = 0.5,
        progress_callback: Optional[Callable[[TaskProgress], None]] = None,
    ):
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.progress_callback = progress_callback
        self.state = TaskState.PENDING
        self.active_plan: Optional[TaskPlan] = None

    def start_task(self, plan: TaskPlan) -> None:
        """Initialize and start task workflow execution."""
        self.active_plan = plan
        # Cancellation only applies to the task that was active when the
        # user cancelled it. A later request must start as runnable.
        self.state = TaskState.RUNNING
        logger.info("[TaskManager] Task started: '%s' (%d steps)", plan.goal, len(plan.steps))
        self._notify_progress(0, len(plan.steps), "Task started")

    def execute_step_with_retry(
        self,
        step_func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Part 6 Retry Engine: Execute a task step with exponential backoff retries on failure."""
        attempt = 0
        last_exception: Optional[Exception] = None

        while attempt < self.max_retries:
            if self.state == TaskState.CANCELLED:
                logger.warning("[TaskManager] Aborting retry execution due to cancellation.")
                raise RuntimeError("Task execution cancelled by user.")
            attempt += 1
            try:
                if attempt > 1:
                    self.state = TaskState.RETRYING
                    logger.info("[TaskManager] Retrying step (Attempt %d/%d)...", attempt, self.max_retries)
                    self._notify_progress(
                        self.active_plan.current_step_index if self.active_plan else 0,
                        len(self.active_plan.steps) if self.active_plan else 1,
                        f"Retrying (attempt {attempt}/{self.max_retries})",
                    )

                result = step_func(*args, **kwargs)
                self.state = TaskState.RUNNING
                return result
            except Exception as exc:
                if self.state == TaskState.CANCELLED:
                    raise RuntimeError("Task execution cancelled by user.") from exc
                last_exception = exc
                logger.warning("[TaskManager] Step attempt %d/%d failed: %s", attempt, self.max_retries, exc)

                if attempt < self.max_retries:
                    # Exponential Backoff Delay (split into short checks for responsive cancellation)
                    backoff = self.initial_backoff_sec * (2 ** (attempt - 1))
                    logger.info("[TaskManager] Exponential backoff delay: %.2f seconds", backoff)
                    sleep_interval = 0.1
                    elapsed = 0.0
                    while elapsed < backoff:
                        if self.state == TaskState.CANCELLED:
                            raise RuntimeError("Task execution cancelled by user.")
                        time.sleep(sleep_interval)
                        elapsed += sleep_interval


        self.state = TaskState.FAILED
        msg = f"Task step failed after {self.max_retries} attempts: {last_exception}"
        logger.error("[TaskManager] %s", msg)
        raise RuntimeError(msg) from last_exception

    def advance_step(self, step_output: str) -> None:
        """Mark current step completed and advance plan progress."""
        if not self.active_plan or self.active_plan.is_complete:
            return

        idx = self.active_plan.current_step_index
        if idx < len(self.active_plan.steps):
            step = self.active_plan.steps[idx]
            step.status = "completed"
            step.result_output = step_output
            self.active_plan.current_step_index += 1

        total = len(self.active_plan.steps)
        current = self.active_plan.current_step_index
        if current >= total:
            self.state = TaskState.SUCCESS
            self._notify_progress(total, total, "Task completed successfully")
        else:
            self._notify_progress(current, total, f"Step {current}/{total} completed")

    def cancel_task(self) -> None:
        """Cancel active task workflow."""
        self.state = TaskState.CANCELLED
        logger.warning("[TaskManager] Task execution cancelled by user")
        if self.active_plan:
            self._notify_progress(
                self.active_plan.current_step_index,
                len(self.active_plan.steps),
                "Task cancelled",
            )

    def get_progress(self) -> TaskProgress:
        """Return current progress snapshot."""
        if not self.active_plan or not self.active_plan.steps:
            return TaskProgress(0, 0, 0.0, self.state, "No active plan")

        total = len(self.active_plan.steps)
        current = min(self.active_plan.current_step_index, total)
        percentage = round((current / total) * 100.0, 1)
        return TaskProgress(current, total, percentage, self.state, f"Task {current} of {total} ({percentage}%)")

    def _notify_progress(self, current: int, total: int, message: str) -> None:
        total_steps = max(1, total)
        percentage = round((current / total_steps) * 100.0, 1)
        progress = TaskProgress(current, total_steps, percentage, self.state, message)

        logger.info("[ProgressTracking] Progress: %s - %s", progress.message, message)
        if self.progress_callback:
            try:
                self.progress_callback(progress)
            except Exception as exc:
                logger.warning("[TaskManager] Progress callback exception: %s", exc)
