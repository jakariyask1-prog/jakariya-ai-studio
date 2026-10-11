"""Unit tests for ContextManager, TaskState, Retry Engine, and Progress Tracking (Parts 4, 5, 6, 7, 10)."""

import unittest
from app.agent.context.context_manager import AgentContextManager
from app.agent.task.task_state import TaskState
from app.agent.task.task_manager import TaskManager, TaskProgress
from app.agent.planner.task_planner import TaskPlan, TaskPlanStep
from app.uploads.file_service import UploadedFile
from pathlib import Path


class TestAgentContextAndTask(unittest.TestCase):
    def test_agent_context_manager_messages_and_memory(self):
        ctx = AgentContextManager(conversation_id="conv_123")
        ctx.add_user_message("Hello Agent")
        ctx.add_assistant_message("Hello User")

        history = ctx.get_formatted_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].content, "Hello Agent")

        ctx.set_memory("last_executed_tool", "python_interpreter")
        self.assertEqual(ctx.get_memory("last_executed_tool"), "python_interpreter")

    def test_task_manager_progress_tracking(self):
        progress_snapshots = []

        def on_progress(p: TaskProgress):
            progress_snapshots.append(p)

        mgr = TaskManager(progress_callback=on_progress)
        plan = TaskPlan(
            goal="Process data",
            steps=[
                TaskPlanStep(1, "Step 1", status="pending"),
                TaskPlanStep(2, "Step 2", status="pending"),
            ],
        )

        mgr.start_task(plan)
        self.assertEqual(mgr.state, TaskState.RUNNING)

        mgr.advance_step("Step 1 output")
        prog1 = mgr.get_progress()
        self.assertEqual(prog1.percentage, 50.0)

        mgr.advance_step("Step 2 output")
        prog2 = mgr.get_progress()
        self.assertEqual(prog2.percentage, 100.0)
        self.assertEqual(mgr.state, TaskState.SUCCESS)

    def test_retry_engine_exponential_backoff(self):
        mgr = TaskManager(max_retries=3, initial_backoff_sec=0.01)

        attempts = 0

        def flaky_func():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise ValueError("Temporary glitch")
            return "Recovered!"

        plan = TaskPlan(goal="Retry test", steps=[TaskPlanStep(1, "Flaky step")])
        mgr.start_task(plan)

        result = mgr.execute_step_with_retry(flaky_func)
        self.assertEqual(result, "Recovered!")
        self.assertEqual(attempts, 3)
        self.assertEqual(mgr.state, TaskState.RUNNING)


if __name__ == "__main__":
    unittest.main()
