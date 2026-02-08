"""Base agent class with lifecycle management."""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from src.mqtt.client import mqtt_client
from src.mqtt.topics import Topics

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPED = "stopped"


class BaseAgent(ABC):
    """Base class for all agents in the system."""

    def __init__(self, agent_id: str, display_name: str):
        self.agent_id = agent_id
        self.display_name = display_name
        self._status = AgentStatus.STOPPED
        self._last_action: str = ""
        self._last_reasoning: str = ""
        self._last_run: datetime | None = None
        self._task: asyncio.Task | None = None
        self._error: str | None = None

    @property
    def status(self) -> AgentStatus:
        return self._status

    @property
    def info(self) -> dict[str, Any]:
        """Get agent info for the frontend."""
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "status": self._status.value,
            "last_action": self._last_action,
            "last_reasoning": self._last_reasoning,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "error": self._error,
        }

    async def start(self) -> None:
        """Start the agent's main loop."""
        self._status = AgentStatus.RUNNING
        self._error = None
        await self._publish_status()
        logger.info(f"Agent {self.agent_id} started")

    async def stop(self) -> None:
        """Stop the agent."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._status = AgentStatus.STOPPED
        await self._publish_status()
        logger.info(f"Agent {self.agent_id} stopped")

    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        """Execute the agent's main logic. Override in subclasses."""
        pass

    def _record_action(self, action: str, reasoning: str = "") -> None:
        """Record the last action and reasoning for inspection."""
        self._last_action = action
        self._last_reasoning = reasoning
        self._last_run = datetime.now()

    async def _publish_status(self) -> None:
        """Publish agent status to MQTT."""
        topic = Topics.agent_status(self.agent_id)
        await mqtt_client.publish(topic, self.info)
