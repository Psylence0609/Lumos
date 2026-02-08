"""Pre-built simulation scenarios for one-click testing."""

import logging
from typing import Any

from src.simulation.overrides import sim_overrides
from src.agents.threat_assessment import threat_agent
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)


class Scenario:
    """Defines a pre-built simulation scenario."""

    def __init__(self, scenario_id: str, name: str, description: str):
        self.scenario_id = scenario_id
        self.name = name
        self.description = description

    async def execute(self) -> dict[str, Any]:
        raise NotImplementedError


class SummerHeatWave(Scenario):
    def __init__(self):
        super().__init__(
            "summer_heat_wave",
            "Summer Heat Wave",
            "Extreme heat (108°F), high grid demand (92%), elevated energy prices. "
            "Tests pre-cooling, battery management, and energy conservation."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_weather(
            temperature_f=108,
            humidity=25,
            wind_speed_mph=8,
            description="extreme heat warning",
            alerts=["Excessive Heat Warning: 108°F expected"],
            forecast_high_f=112,
            forecast_low_f=88,
        )
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=92,
            lmp_price=150,
            system_load_mw=72000,
            operating_reserves_mw=2100,
            grid_alert_level="conservation",
        )
        await sim_overrides.set_battery_level(45)
        # Trigger reassessment
        await threat_agent.run()
        return {"scenario": self.scenario_id, "status": "active"}


class WinterStorm(Scenario):
    def __init__(self):
        super().__init__(
            "winter_storm",
            "Winter Storm Uri",
            "Freezing temps (15°F), grid near collapse (97%), rolling outages imminent. "
            "Tests heating management, battery backup, and critical device prioritization."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_weather(
            temperature_f=15,
            humidity=80,
            wind_speed_mph=25,
            description="winter storm warning with ice",
            alerts=["Winter Storm Warning", "Wind Chill Advisory: -5°F"],
            forecast_high_f=20,
            forecast_low_f=5,
        )
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=97,
            lmp_price=9000,
            system_load_mw=78000,
            operating_reserves_mw=800,
            grid_alert_level="eea3",
        )
        await sim_overrides.set_battery_level(30)
        await threat_agent.run()
        return {"scenario": self.scenario_id, "status": "active"}


class GridEmergency(Scenario):
    def __init__(self):
        super().__init__(
            "grid_emergency",
            "Grid Emergency",
            "ERCOT declares EEA3, rotating outages in progress. "
            "Tests maximum energy conservation and battery backup mode."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=99,
            lmp_price=5000,
            system_load_mw=80000,
            operating_reserves_mw=500,
            grid_alert_level="eea3",
        )
        await sim_overrides.set_battery_level(20)
        await sim_overrides.set_solar_generation(0)
        await threat_agent.run()
        return {"scenario": self.scenario_id, "status": "active"}


class UserLeavesHome(Scenario):
    def __init__(self):
        super().__init__(
            "user_leaves_home",
            "User Leaves Home",
            "User GPS shows away from home. "
            "Tests away-mode: non-essential devices off, security armed, eco mode."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_gps_location("away")
        return {"scenario": self.scenario_id, "status": "active"}


class UserArrivesHome(Scenario):
    def __init__(self):
        super().__init__(
            "user_arrives_home",
            "User Arrives Home",
            "User GPS shows arriving within geofence. "
            "Tests welcome-home: lights on, temperature adjust, unlock door."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_gps_location("arriving")
        return {"scenario": self.scenario_id, "status": "active"}


class BedtimeRoutine(Scenario):
    def __init__(self):
        super().__init__(
            "bedtime_routine",
            "Bedtime Routine",
            "Simulate 11 PM bedtime. "
            "Tests: dim lights, lock doors, lower thermostat, set alarms."
        )

    async def execute(self) -> dict[str, Any]:
        from src.agents.orchestrator import orchestrator
        await orchestrator.handle_user_command(
            "I'm going to sleep. Please set up the house for bedtime."
        )
        return {"scenario": self.scenario_id, "status": "active"}


class MorningRoutine(Scenario):
    def __init__(self):
        super().__init__(
            "morning_routine",
            "Morning Routine",
            "Simulate 7 AM wake up. "
            "Tests: lights on, coffee brewing, thermostat up, unlock door."
        )

    async def execute(self) -> dict[str, Any]:
        from src.agents.orchestrator import orchestrator
        await orchestrator.handle_user_command(
            "Good morning! Please start my morning routine."
        )
        return {"scenario": self.scenario_id, "status": "active"}


class UpcomingMeeting(Scenario):
    def __init__(self):
        super().__init__(
            "upcoming_meeting",
            "Upcoming Meeting (7 min)",
            "Injects a calendar event 'Team Standup' starting in 7 minutes. "
            "Tests preparing_for_meeting mode: office setup, non-essential dimming, DND prep."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_calendar_event(
            summary="Team Standup",
            starts_in_minutes=7,
            duration_minutes=30,
            location="Zoom",
        )
        return {"scenario": self.scenario_id, "status": "active"}


class InMeeting(Scenario):
    def __init__(self):
        super().__init__(
            "in_meeting",
            "Currently In Meeting",
            "Injects a calendar event that is already in progress. "
            "Tests do_not_disturb mode: voice suppression, lights off, focus environment."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.set_calendar_event(
            summary="Product Review Call",
            starts_in_minutes=-5,  # started 5 min ago
            duration_minutes=45,
            location="Google Meet",
        )
        return {"scenario": self.scenario_id, "status": "active"}


class MeetingEnds(Scenario):
    def __init__(self):
        super().__init__(
            "meeting_ends",
            "Meeting Ends (Restore Normal)",
            "Clears the calendar override, ending any active meeting. "
            "Tests normal mode restoration: lights restored, DND off, devices back to comfort."
        )

    async def execute(self) -> dict[str, Any]:
        await sim_overrides.clear_calendar_override()
        return {"scenario": self.scenario_id, "status": "active"}


# Registry of all scenarios
SCENARIOS: dict[str, Scenario] = {
    "summer_heat_wave": SummerHeatWave(),
    "winter_storm": WinterStorm(),
    "grid_emergency": GridEmergency(),
    "user_leaves_home": UserLeavesHome(),
    "user_arrives_home": UserArrivesHome(),
    "upcoming_meeting": UpcomingMeeting(),
    "in_meeting": InMeeting(),
    "meeting_ends": MeetingEnds(),
    "bedtime_routine": BedtimeRoutine(),
    "morning_routine": MorningRoutine(),
}


def get_scenario_list() -> list[dict[str, str]]:
    """Get list of all available scenarios."""
    return [
        {
            "id": s.scenario_id,
            "name": s.name,
            "description": s.description,
        }
        for s in SCENARIOS.values()
    ]
