"""Task handle exchanged between the master agent and MCP tools."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskRequest:
    task: str
    model: str
    reasoning_effort: str | None = None

    def __post_init__(self) -> None:
        if not self.task.strip():
            raise ValueError("task must not be empty")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if self.reasoning_effort is not None and not self.reasoning_effort.strip():
            raise ValueError("reasoning_effort must not be empty when supplied")


@dataclass(frozen=True)
class Task:
    task_id: str
    pid: int

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[0-9a-f]{32}", self.task_id):
            raise ValueError("Invalid task ID: expected the ID returned by start_task")
        if type(self.pid) is not int or self.pid <= 0:
            raise ValueError("Task PID must be a positive integer")


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    state: str
    delivery_directory: str
    files: list[str]
    patch_file: str | None
    report_file: str | None


@dataclass(frozen=True)
class ExecutionSummary:
    task_id: str
    pid: int | None
    state: str
    running: bool
    sandbox: str | None
    cleaned: bool
    error: str | None = None


@dataclass(frozen=True)
class CleanupResult:
    task_id: str
    sandbox_removed: bool
    checkout_removed: bool
    artifacts_deleted: bool
    delivery_directory: str | None
