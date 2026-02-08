"""Pydantic models for device state and configuration.

Includes a centralized DEVICE_TYPE_ACTIONS schema that serves as the single
source of truth for all LLM prompts across agents — no more duplicated
device-action references.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PriorityTier(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    OPTIONAL = "optional"


class DeviceType(str, Enum):
    LIGHT = "light"
    THERMOSTAT = "thermostat"
    LOCK = "lock"
    BATTERY = "battery"
    COFFEE_MAKER = "coffee_maker"
    SENSOR = "sensor"
    SMART_PLUG = "smart_plug"
    WATER_HEATER = "water_heater"


# ---------------------------------------------------------------------------
# Centralized action schema per device type.
#
# This is the SINGLE SOURCE OF TRUTH for what actions each device type
# supports and what parameters they accept.  Every LLM prompt in the system
# (orchestrator, pattern detector, preference parser, …) is auto-generated
# from this dict — so adding a new device type or action only requires
# editing this one place.
# ---------------------------------------------------------------------------

DEVICE_TYPE_ACTIONS: dict[str, list[dict[str, Any]]] = {
    "light": [
        {"action": "on", "params": {"brightness": "0-100"}},
        {"action": "off", "params": {}},
        {"action": "dim", "params": {"brightness": "0-100"}},
        {"action": "color", "params": {"r": "0-255", "g": "0-255", "b": "0-255"}},
    ],
    "thermostat": [
        {"action": "set_temperature", "params": {"temperature": "60-85"}},
        {"action": "set_mode", "params": {"mode": "heat|cool|auto|eco|off"}},
        {"action": "eco_mode", "params": {}},
    ],
    "smart_plug": [
        {"action": "on", "params": {}},
        {"action": "off", "params": {}},
    ],
    "lock": [
        {"action": "lock", "params": {}},
        {"action": "unlock", "params": {}},
    ],
    "coffee_maker": [
        {"action": "brew", "params": {"strength": "light|medium|strong"}},
        {"action": "off", "params": {}},
        {"action": "keep_warm", "params": {}},
    ],
    "battery": [
        {"action": "set_mode", "params": {"mode": "charge|discharge|auto|backup"}},
    ],
    "water_heater": [
        {"action": "heat", "params": {"temperature_f": "100-160"}},
        {"action": "boost", "params": {"temperature_f": "140"}},
        {"action": "standby", "params": {}},
        {"action": "off", "params": {}},
    ],
    "sensor": [],  # read-only, no actions
}


def build_action_reference_text() -> str:
    """Build the device action reference block for LLM prompts.

    Returns plain text (with real braces).  The caller is responsible for
    escaping if the text is embedded inside a Python ``.format()`` template.
    """
    lines: list[str] = []
    for type_str, actions in DEVICE_TYPE_ACTIONS.items():
        if not actions:
            lines.append(f"- {type_str}: read-only, no actions")
            continue
        parts: list[str] = []
        for a in actions:
            if a["params"]:
                p = ", ".join(f'"{k}": {v}' for k, v in a["params"].items())
                parts.append(f'"{a["action"]}" (params: {{{p}}})')
            else:
                parts.append(f'"{a["action"]}"')
        lines.append(f"- {type_str}: {', '.join(parts)}")
    return "\n".join(lines)


class ThermostatMode(str, Enum):
    HEAT = "heat"
    COOL = "cool"
    AUTO = "auto"
    ECO = "eco"
    OFF = "off"


class BatteryMode(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"
    AUTO = "auto"
    BACKUP = "backup"


class EnergyProfile(BaseModel):
    idle_watts: float = 0.0
    active_watts: float = 0.0


class DeviceConfig(BaseModel):
    """Configuration for a device loaded from YAML."""
    id: str
    type: DeviceType
    display_name: str
    capabilities: list[str] = []
    energy_profile: EnergyProfile = EnergyProfile()
    priority_tier: PriorityTier = PriorityTier.MEDIUM
    negotiation_flexibility: float = 0.5
    room: str = ""
    sensor_type: str | None = None
    battery_capacity_kwh: float | None = None
    solar_panel_watts: float | None = None


class DeviceState(BaseModel):
    """Current state of a device."""
    device_id: str
    device_type: DeviceType
    display_name: str
    room: str
    online: bool = True
    power: bool = False
    last_updated: datetime = Field(default_factory=datetime.now)
    properties: dict[str, Any] = {}
    energy_profile: EnergyProfile = EnergyProfile()
    priority_tier: PriorityTier = PriorityTier.MEDIUM
    negotiation_flexibility: float = 0.5
    current_watts: float = 0.0

    def to_mqtt_payload(self) -> dict[str, Any]:
        """Convert state to MQTT-friendly dict."""
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "display_name": self.display_name,
            "room": self.room,
            "online": self.online,
            "power": self.power,
            "properties": self.properties,
            "current_watts": self.current_watts,
            "priority_tier": self.priority_tier.value,
            "last_updated": self.last_updated.isoformat(),
        }


class DeviceCommand(BaseModel):
    """Command sent to a device."""
    device_id: str
    action: str
    parameters: dict[str, Any] = {}
    source: str = "orchestrator"
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: str | None = None
