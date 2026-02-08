"""Simulation control API routes."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.simulation.engine import sim_engine
from src.simulation.overrides import sim_overrides
from src.simulation.scenarios import get_scenario_list

router = APIRouter(prefix="/simulation", tags=["simulation"])


# -- Request models --

class GPSOverride(BaseModel):
    location: str  # home, away, arriving, leaving

class GPSCoordinates(BaseModel):
    lat: float
    lon: float

class WeatherOverride(BaseModel):
    temperature_f: float = 75
    humidity: float = 50
    wind_speed_mph: float = 5
    description: str = "clear"
    alerts: list[str] = []
    forecast_high_f: float | None = None
    forecast_low_f: float | None = None

class GridOverride(BaseModel):
    load_capacity_pct: float = 65
    lmp_price: float = 25
    system_load_mw: float = 45000
    operating_reserves_mw: float = 3000
    grid_alert_level: str = "normal"

class BatteryOverride(BaseModel):
    battery_pct: float = 75

class SolarOverride(BaseModel):
    watts: float = 0

class DeviceFailure(BaseModel):
    device_id: str
    offline: bool

class TimeMultiplier(BaseModel):
    multiplier: float = 1.0

class CalendarOverride(BaseModel):
    summary: str = "Team Meeting"
    starts_in_minutes: int = 7
    duration_minutes: int = 30
    location: str = ""

class ScenarioRequest(BaseModel):
    scenario_id: str


# -- Status --

@router.get("/status")
async def get_simulation_status() -> dict[str, Any]:
    """Get current simulation status including active overrides and scenarios."""
    return sim_engine.get_status()


@router.get("/scenarios")
async def list_scenarios() -> list[dict[str, str]]:
    """Get all available pre-built scenarios."""
    return get_scenario_list()


# -- GPS --

@router.post("/gps/location")
async def set_gps_location(req: GPSOverride) -> dict[str, Any]:
    return await sim_overrides.set_gps_location(req.location)

@router.post("/gps/coordinates")
async def set_gps_coordinates(req: GPSCoordinates) -> dict[str, Any]:
    return await sim_overrides.set_gps_coordinates(req.lat, req.lon)

@router.delete("/gps")
async def clear_gps() -> dict[str, Any]:
    return await sim_overrides.clear_gps_override()


# -- Weather --

@router.post("/weather")
async def set_weather(req: WeatherOverride) -> dict[str, Any]:
    return await sim_overrides.set_weather(**req.model_dump())

@router.delete("/weather")
async def clear_weather() -> dict[str, Any]:
    return await sim_overrides.clear_weather_override()


# -- Grid --

@router.post("/grid")
async def set_grid(req: GridOverride) -> dict[str, Any]:
    return await sim_overrides.set_grid_conditions(**req.model_dump())

@router.delete("/grid")
async def clear_grid() -> dict[str, Any]:
    return await sim_overrides.clear_grid_override()


# -- Battery/Solar --

@router.post("/battery")
async def set_battery(req: BatteryOverride) -> dict[str, Any]:
    return await sim_overrides.set_battery_level(req.battery_pct)

@router.post("/solar")
async def set_solar(req: SolarOverride) -> dict[str, Any]:
    return await sim_overrides.set_solar_generation(req.watts)


# -- Calendar --

@router.post("/calendar")
async def set_calendar_event(req: CalendarOverride) -> dict[str, Any]:
    return await sim_overrides.set_calendar_event(**req.model_dump())

@router.delete("/calendar")
async def clear_calendar() -> dict[str, Any]:
    return await sim_overrides.clear_calendar_override()


# -- Device Failure --

@router.post("/device-failure")
async def set_device_failure(req: DeviceFailure) -> dict[str, Any]:
    return await sim_overrides.set_device_failure(req.device_id, req.offline)


# -- Time --

@router.post("/time")
async def set_time_multiplier(req: TimeMultiplier) -> dict[str, Any]:
    return sim_engine.set_time_multiplier(req.multiplier)


# -- Scenarios --

@router.post("/scenarios/run")
async def run_scenario(req: ScenarioRequest) -> dict[str, Any]:
    return await sim_engine.run_scenario(req.scenario_id)

@router.post("/scenarios/stop")
async def stop_scenario() -> dict[str, Any]:
    return await sim_engine.stop_scenario()


# -- Clear All --

@router.delete("/overrides")
async def clear_all_overrides() -> dict[str, Any]:
    return await sim_overrides.clear_all()
