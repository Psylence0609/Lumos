"""Pydantic models for event logging."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    DEVICE_STATE_CHANGE = "device_state_change"
    DEVICE_COMMAND = "device_command"
    AGENT_DECISION = "agent_decision"
    THREAT_ASSESSMENT = "threat_assessment"
    PATTERN_DETECTED = "pattern_detected"
    USER_ACTION = "user_action"
    SYSTEM_EVENT = "system_event"
    SIMULATION_OVERRIDE = "simulation_override"
    VOICE_ALERT = "voice_alert"
    ENERGY_EVENT = "energy_event"


class Event(BaseModel):
    """A logged system event."""
    event_id: str = ""
    event_type: EventType
    source: str = ""
    data: dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }
