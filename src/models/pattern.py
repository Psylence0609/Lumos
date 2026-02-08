"""Pydantic models for pattern detection and learning."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PatternType(str, Enum):
    ROUTINE = "routine"
    PREFERENCE = "preference"
    ENERGY = "energy"
    USER_DEFINED = "user_defined"  # Explicitly taught by the user via chat


class PatternAction(BaseModel):
    """Single action in a pattern sequence."""
    device_id: str
    action: str
    parameters: dict = {}
    delay_seconds: float = 0.0


class DetectedPattern(BaseModel):
    """A detected usage pattern."""
    pattern_id: str
    pattern_type: PatternType
    display_name: str = ""
    description: str = ""
    frequency: int = 0
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    trigger_conditions: dict = {}
    action_sequence: list[PatternAction] = []
    approved: bool = False
    last_occurrence: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)
    source_utterance: str = ""  # The original user message that created this pattern

    def is_ready_to_suggest(self) -> bool:
        """Whether pattern has enough data to suggest automation."""
        # User-defined patterns are always ready (user explicitly taught them)
        if self.pattern_type == PatternType.USER_DEFINED:
            return True
        return self.frequency >= 3 and self.confidence >= 0.8

    def to_persist_dict(self) -> dict[str, Any]:
        """Serialize to a dict for SQLite storage."""
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "display_name": self.display_name,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "trigger_conditions": self.trigger_conditions,
            "action_sequence": [a.model_dump() for a in self.action_sequence],
            "approved": self.approved,
            "last_occurrence": self.last_occurrence.isoformat(),
            "created_at": self.created_at.isoformat(),
            "source_utterance": self.source_utterance,
        }

    @classmethod
    def from_persist_dict(cls, data: dict[str, Any]) -> "DetectedPattern":
        """Deserialize from a SQLite-stored dict."""
        return cls(
            pattern_id=data["pattern_id"],
            pattern_type=PatternType(data.get("pattern_type", "routine")),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            frequency=data.get("frequency", 0),
            confidence=data.get("confidence", 0.0),
            trigger_conditions=data.get("trigger_conditions", {}),
            action_sequence=[
                PatternAction(**a) for a in data.get("action_sequence", [])
            ],
            approved=data.get("approved", False),
            last_occurrence=datetime.fromisoformat(data["last_occurrence"])
            if data.get("last_occurrence") else datetime.now(),
            created_at=datetime.fromisoformat(data["created_at"])
            if data.get("created_at") else datetime.now(),
            source_utterance=data.get("source_utterance", ""),
        )
