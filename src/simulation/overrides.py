"""Simulation override manager -- GPS, weather, grid, battery, calendar overrides."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.agents.user_info import user_info_agent
from src.integrations.openweather import weather_client
from src.integrations.ercot import ercot_client
from src.integrations.google_calendar import calendar_client, CalendarEvent
from src.devices.registry import device_registry
from src.models.threat import WeatherData, ERCOTData
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)


class SimulationOverrides:
    """Manages all simulation overrides from the control panel."""

    def __init__(self):
        self._active_overrides: dict[str, Any] = {}

    @property
    def active(self) -> dict[str, Any]:
        return self._active_overrides

    # -- GPS Overrides --

    async def set_gps_location(self, location: str) -> dict[str, Any]:
        """Override user GPS location and trigger immediate orchestrator response."""
        user_info_agent.set_location_override(location)
        self._active_overrides["gps_location"] = location
        await ws_manager.broadcast(
            "simulation_override", {"type": "gps", "location": location}
        )
        logger.info(f"GPS override: {location}")

        # Force immediate user info update so the transition is detected
        await user_info_agent.run()

        # Trigger orchestrator to handle the location change immediately
        from src.agents.orchestrator import orchestrator

        asyncio.create_task(orchestrator.handle_location_change(location))

        return {"success": True, "location": location}

    async def set_gps_coordinates(self, lat: float, lon: float) -> dict[str, Any]:
        """Override GPS coordinates."""
        user_info_agent.set_gps_coordinates(lat, lon)
        self._active_overrides["gps_coords"] = {"lat": lat, "lon": lon}
        await ws_manager.broadcast(
            "simulation_override", {"type": "gps_coords", "lat": lat, "lon": lon}
        )

        # Trigger immediate user info update
        await user_info_agent.run()

        return {"success": True, "lat": lat, "lon": lon}

    async def clear_gps_override(self) -> dict[str, Any]:
        user_info_agent.clear_location_override()
        self._active_overrides.pop("gps_location", None)
        self._active_overrides.pop("gps_coords", None)

        # Trigger location re-evaluation (back to home)
        await user_info_agent.run()
        from src.agents.orchestrator import orchestrator

        # Reset the dedup so "home" transition is handled
        orchestrator._last_location_handled = None
        asyncio.create_task(
            orchestrator.handle_location_change(user_info_agent.location.value)
        )
        return {"success": True}

    # -- Weather Overrides --

    async def set_weather(
        self,
        temperature_f: float = 75,
        humidity: float = 50,
        wind_speed_mph: float = 5,
        description: str = "clear",
        alerts: list[str] | None = None,
        forecast_high_f: float | None = None,
        forecast_low_f: float | None = None,
    ) -> dict[str, Any]:
        """Override weather data and trigger immediate threat reassessment."""
        data = WeatherData(
            temperature_f=temperature_f,
            feels_like_f=temperature_f,
            humidity=humidity,
            wind_speed_mph=wind_speed_mph,
            description=description,
            alerts=alerts or [],
            forecast_high_f=forecast_high_f or temperature_f + 5,
            forecast_low_f=forecast_low_f or temperature_f - 10,
        )
        weather_client.set_override(data)
        self._active_overrides["weather"] = {
            "temperature_f": temperature_f,
            "humidity": humidity,
            "description": description,
        }
        await ws_manager.broadcast(
            "simulation_override",
            {"type": "weather", "data": self._active_overrides["weather"]},
        )
        logger.info(f"Weather override: {temperature_f}°F, {description}")

        # Trigger immediate threat reassessment with the new weather data
        from src.agents.threat_assessment import threat_agent

        asyncio.create_task(threat_agent.run())

        return {"success": True, "weather": data.model_dump()}

    async def clear_weather_override(self) -> dict[str, Any]:
        weather_client.clear_override()
        self._active_overrides.pop("weather", None)

        # Reassess with real weather data
        from src.agents.threat_assessment import threat_agent

        asyncio.create_task(threat_agent.run())
        return {"success": True}

    # -- ERCOT Grid Overrides --

    async def set_grid_conditions(
        self,
        load_capacity_pct: float = 65,
        lmp_price: float = 25,
        system_load_mw: float = 45000,
        operating_reserves_mw: float = 3000,
        grid_alert_level: str = "normal",
    ) -> dict[str, Any]:
        """Override ERCOT grid conditions and trigger immediate threat reassessment."""
        data = ERCOTData(
            system_load_mw=system_load_mw,
            load_capacity_pct=load_capacity_pct,
            lmp_price=lmp_price,
            operating_reserves_mw=operating_reserves_mw,
            grid_alert_level=grid_alert_level,
        )
        ercot_client.set_override(data)
        self._active_overrides["ercot"] = {
            "load_capacity_pct": load_capacity_pct,
            "lmp_price": lmp_price,
            "grid_alert_level": grid_alert_level,
        }
        await ws_manager.broadcast(
            "simulation_override",
            {"type": "ercot", "data": self._active_overrides["ercot"]},
        )
        logger.info(
            f"ERCOT override: {load_capacity_pct}% load, ${lmp_price}/MWh, {grid_alert_level}"
        )

        # Trigger immediate threat reassessment with the new grid data
        from src.agents.threat_assessment import threat_agent

        asyncio.create_task(threat_agent.run())

        return {"success": True, "ercot": data.model_dump()}

    async def clear_grid_override(self) -> dict[str, Any]:
        ercot_client.clear_override()
        self._active_overrides.pop("ercot", None)

        # Reassess with real grid data
        from src.agents.threat_assessment import threat_agent

        asyncio.create_task(threat_agent.run())
        return {"success": True}

    # -- Battery / Solar Overrides --

    async def set_battery_level(self, level: float) -> dict[str, Any]:
        """Override battery level (0-100%)."""
        device = device_registry.get_device("battery_main")
        if device:
            result = await device.execute_action("set_battery_level", {"level": level})
            self._active_overrides["battery_level"] = level
            await ws_manager.broadcast(
                "simulation_override", {"type": "battery", "level": level}
            )
            return {"success": True, "battery_pct": level}
        return {"success": False, "error": "Battery device not found"}

    async def set_solar_generation(self, watts: float) -> dict[str, Any]:
        """Override solar generation."""
        device = device_registry.get_device("battery_main")
        if device:
            result = await device.execute_action(
                "set_solar_generation", {"watts": watts}
            )
            self._active_overrides["solar_watts"] = watts
            await ws_manager.broadcast(
                "simulation_override", {"type": "solar", "watts": watts}
            )
            return {"success": True, "solar_watts": watts}
        return {"success": False, "error": "Battery device not found"}

    # -- Device Failure Overrides --

    async def set_device_failure(
        self, device_id: str, offline: bool
    ) -> dict[str, Any]:
        """Force a device offline or back online."""
        device = device_registry.get_device(device_id)
        if not device:
            return {"success": False, "error": f"Device not found: {device_id}"}

        device.set_forced_offline(offline)
        key = f"device_failure_{device_id}"
        if offline:
            self._active_overrides[key] = True
        else:
            self._active_overrides.pop(key, None)

        await ws_manager.broadcast(
            "simulation_override",
            {"type": "device_failure", "device_id": device_id, "offline": offline},
        )
        await ws_manager.broadcast("device_state", device.get_state_dict())
        return {"success": True, "device_id": device_id, "offline": offline}

    # -- Calendar Overrides --

    async def set_calendar_event(
        self,
        summary: str = "Team Meeting",
        starts_in_minutes: int = 7,
        duration_minutes: int = 30,
        location: str = "",
    ) -> dict[str, Any]:
        """Inject a simulated calendar event and trigger immediate context update.

        Args:
            summary: Event name (keywords like 'meeting', 'call' trigger DND)
            starts_in_minutes: How many minutes from now the event starts
                - Use 0 or negative to simulate being *inside* a meeting
            duration_minutes: How long the event lasts
            location: Optional event location (e.g. "Zoom", "Conference Room")
        """
        now = datetime.now(timezone.utc)
        start = now + timedelta(minutes=starts_in_minutes)
        end = start + timedelta(minutes=duration_minutes)

        event = CalendarEvent(
            event_id=f"sim_{int(now.timestamp())}",
            summary=summary,
            start=start,
            end=end,
            location=location,
        )

        calendar_client.set_override([event])
        self._active_overrides["calendar"] = {
            "summary": summary,
            "starts_in_minutes": starts_in_minutes,
            "duration_minutes": duration_minutes,
        }
        await ws_manager.broadcast(
            "simulation_override",
            {
                "type": "calendar",
                "summary": summary,
                "starts_in_minutes": starts_in_minutes,
                "duration_minutes": duration_minutes,
            },
        )
        logger.info(
            f"Calendar override: '{summary}' in {starts_in_minutes}min "
            f"({duration_minutes}min duration)"
        )

        # Force user info agent to pick up the new calendar immediately
        await user_info_agent.run()

        return {
            "success": True,
            "event": {
                "summary": summary,
                "start": start.isoformat(),
                "end": end.isoformat(),
                "location": location,
            },
        }

    async def clear_calendar_override(self) -> dict[str, Any]:
        """Clear calendar override and trigger mode restoration."""
        calendar_client.clear_override()
        self._active_overrides.pop("calendar", None)
        await ws_manager.broadcast("simulation_override", {"type": "calendar_clear"})

        # Force user info agent to re-evaluate — this will set suggested_mode
        # back to "normal" (no events), which the orchestrator will pick up
        # and trigger a mode restoration.
        await user_info_agent.run()

        # Also reset the orchestrator's tracked mode so it detects the transition
        from src.agents.orchestrator import orchestrator
        # Don't reset the mode directly — let the next _check_and_respond cycle
        # detect the change naturally.

        return {"success": True}

    # -- Clear All --

    async def clear_all(self) -> dict[str, Any]:
        """Clear all simulation overrides."""
        weather_client.clear_override()
        ercot_client.clear_override()
        user_info_agent.clear_location_override()
        calendar_client.clear_override()

        # Restore all devices
        for device in device_registry.devices.values():
            device.set_forced_offline(False)
            device.set_failure_probability(0.0)

        self._active_overrides.clear()
        await ws_manager.broadcast("simulation_override", {"type": "clear_all"})
        return {"success": True}


# Singleton
sim_overrides = SimulationOverrides()
