"""Pydantic models for commands and task execution."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CommandStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class Task(BaseModel):
    """A single device-level task."""
    task_id: str
    target_device_id: str
    action: str
    parameters: dict = {}
    dependencies: list[str] = []
    timeout_seconds: float = 30.0
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None


class Command(BaseModel):
    """A high-level command with execution plan."""
    command_id: str
    user_input: str
    intent: str = ""
    status: CommandStatus = CommandStatus.RECEIVED
    tasks: list[Task] = []
    context: dict = {}
    reasoning: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
