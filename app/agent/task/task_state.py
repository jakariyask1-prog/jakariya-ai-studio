"""Workflow State Engine Enums for Task Execution (Part 5)."""

from enum import Enum


class TaskState(str, Enum):
    """Lifecycle execution states for agent tasks."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    CANCELLED = "CANCELLED"
