"""Pydantic models for device state and configuration."""

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
