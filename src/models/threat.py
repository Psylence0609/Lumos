"""Pydantic models for threat assessment."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ThreatLevel(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    HEAT_WAVE = "heat_wave"
    GRID_STRAIN = "grid_strain"
    POWER_OUTAGE = "power_outage"
    STORM = "storm"
    COLD_SNAP = "cold_snap"
    NONE = "none"


class WeatherData(BaseModel):
    """Current weather data from OpenWeatherMap."""
    temperature_f: float = 0.0
    feels_like_f: float = 0.0
    humidity: float = 0.0
    wind_speed_mph: float = 0.0
    description: str = ""
    alerts: list[str] = []
    forecast_high_f: float = 0.0
    forecast_low_f: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)


class ERCOTData(BaseModel):
    """ERCOT grid conditions data."""
    system_load_mw: float = 0.0
    load_capacity_pct: float = 0.0
    lmp_price: float = 0.0
    operating_reserves_mw: float = 0.0
    grid_alert_level: str = "normal"
    timestamp: datetime = Field(default_factory=datetime.now)


class ThreatAssessment(BaseModel):
    """Structured threat assessment from The Oracle."""
    threat_level: ThreatLevel = ThreatLevel.NONE
    threat_type: ThreatType = ThreatType.NONE
    urgency_score: float = Field(default=0.0, ge=0.0, le=1.0)
    summary: str = ""
    reasoning: str = ""
    recommended_actions: list[str] = []
    weather_data: WeatherData | None = None
    ercot_data: ERCOTData | None = None
    timestamp: datetime = Field(default_factory=datetime.now)

    def requires_user_permission(self) -> bool:
        """Whether this threat level requires user approval before acting."""
        return self.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
