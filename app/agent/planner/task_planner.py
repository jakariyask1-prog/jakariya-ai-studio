"""Task Planner Service for AI Agent Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional
from app.agent.tools.base_tool import BaseTool


@dataclass
class TaskPlanStep:
    """Represents a single step in a task execution plan."""

    step_number: int
    description: str
    tool_name: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed
    result_output: Optional[str] = None


@dataclass
class TaskPlan:
    """Complete goal breakdown with sequential steps."""

    goal: str
    steps: List[TaskPlanStep] = field(default_factory=list)
    current_step_index: int = 0

    @property
    def is_complete(self) -> bool:
        return self.current_step_index >= len(self.steps) or all(s.status == "completed" for s in self.steps)


class TaskPlanner:
    """Decompose complex user requests into executable plan steps."""

    def create_plan(self, goal: str, available_tools: List[BaseTool]) -> TaskPlan:
        """Generate initial structured plan steps based on goal and tools available."""
        clean_goal = goal.strip()
        tool_names = {t.name: t for t in available_tools}

        steps: List[TaskPlanStep] = []
        if "file" in clean_goal.lower() or "save" in clean_goal.lower() or "write" in clean_goal.lower():
            steps.append(TaskPlanStep(1, "Analyze request and prepare content", None))
            if "write_file" in tool_names:
                steps.append(TaskPlanStep(2, "Write output to file", "write_file"))
            if "read_file" in tool_names:
                steps.append(TaskPlanStep(3, "Verify file contents", "read_file"))
        elif "code" in clean_goal.lower() or "python" in clean_goal.lower() or "calculate" in clean_goal.lower():
            steps.append(TaskPlanStep(1, "Draft solution logic", None))
            if "python_interpreter" in tool_names:
                steps.append(TaskPlanStep(2, "Execute Python code snippet", "python_interpreter"))
            steps.append(TaskPlanStep(3, "Synthesize final output", None))
        elif "search" in clean_goal.lower() or "news" in clean_goal.lower() or "find" in clean_goal.lower():
            if "web_search" in tool_names:
                steps.append(TaskPlanStep(1, "Perform real-time web search", "web_search"))
            steps.append(TaskPlanStep(2, "Summarize search results", None))
        else:
            steps.append(TaskPlanStep(1, f"Process goal: {clean_goal}", None))

        return TaskPlan(goal=clean_goal, steps=steps)
