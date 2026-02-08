"""Pre-built simulation scenarios for one-click testing, including temporal demos.

Device references are resolved via the DeviceRegistry so that scenarios
stay in sync with config/devices.yaml without hardcoded IDs.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from src.simulation.overrides import sim_overrides
from src.agents.threat_assessment import threat_agent
from src.api.websocket import ws_manager
from src.models.device import DeviceType
from src.models.pattern import DetectedPattern, PatternType, PatternAction
from src.storage.event_store import event_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Registry-aware device-lookup helpers
# ---------------------------------------------------------------------------

def _device_id(dtype: DeviceType, room: str | None = None, *, fallback: str = "") -> str:
    """Resolve a device ID from the registry by type (and optional room).

    Falls back to *fallback* (a hardcoded ID) when the registry hasn't loaded yet
    (e.g. during module import) so that pattern seed data still works.
    """
    from src.devices.registry import device_registry

    d = device_registry.get_first_device_of_type(dtype, room=room)
    if d:
        return d.device_id
    return fallback


async def _exec(device_id: str, action: str, params: dict | None = None) -> None:
    """Execute a single device action via the home state agent (convenience wrapper)."""
    from src.agents.home_state import home_state_agent
    await home_state_agent.execute_action(device_id, action, params or {})


async def _turn_off_non_essential() -> None:
    """Turn off all non-essential devices using the registry query."""
    from src.devices.registry import device_registry
    from src.agents.home_state import home_state_agent

    for d in device_registry.get_non_essential_devices():
        await home_state_agent.execute_action(d.device_id, "off")


# ---------------------------------------------------------------------------
# Base classes
# ---------------------------------------------------------------------------

class Scenario:
    """Defines a pre-built simulation scenario."""

    def __init__(self, scenario_id: str, name: str, description: str):
        self.scenario_id = scenario_id
        self.name = name
        self.description = description

    async def execute(self, cancel_event: asyncio.Event | None = None) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class TimelineStep:
    """A single step in a temporal scenario."""
    timestamp: str  # Simulated time, e.g. "6:00 AM"
    title: str  # Short title, e.g. "Threat Detection"
    description: str  # What is happening
    actions: list[Callable[[], Coroutine]] = field(default_factory=list)
    pause_seconds: int = 10  # How long to wait after this step
    metrics: dict[str, Any] = field(default_factory=dict)


class TemporalScenario(Scenario):
    """A scenario that unfolds step-by-step with pauses for visual storytelling."""

    def __init__(self, scenario_id: str, name: str, description: str):
        super().__init__(scenario_id, name, description)
        self.steps: list[TimelineStep] = []
        self._patterns_to_seed: list[DetectedPattern] = []

    async def execute(self, cancel_event: asyncio.Event | None = None) -> dict[str, Any]:
        """Execute all steps with pauses between them."""
        # Seed pre-learned patterns
        if self._patterns_to_seed:
            for pattern in self._patterns_to_seed:
                await event_store.save_pattern(
                    pattern.pattern_id, pattern.to_persist_dict()
                )
            await ws_manager.broadcast("pattern_suggestion", {})
            logger.info(
                f"Seeded {len(self._patterns_to_seed)} patterns for {self.scenario_id}"
            )

        total = len(self.steps)
        for i, step in enumerate(self.steps):
            if cancel_event and cancel_event.is_set():
                logger.info(f"Scenario {self.scenario_id} cancelled at step {i}")
                break

            # Broadcast step info to frontend
            await ws_manager.broadcast("scenario_step", {
                "scenario_id": self.scenario_id,
                "current_step": i,
                "total_steps": total,
                "timestamp": step.timestamp,
                "title": step.title,
                "description": step.description,
                "metrics": step.metrics,
                "is_last": i == total - 1,
            })

            logger.info(
                f"[{self.scenario_id}] Step {i + 1}/{total}: "
                f"{step.timestamp} - {step.title}"
            )

            # Execute the step's actions
            for action_fn in step.actions:
                try:
                    await action_fn()
                except Exception:
                    logger.exception(f"Error in step {i} action")

            # Wait before next step (interruptible)
            if cancel_event:
                try:
                    await asyncio.wait_for(
                        cancel_event.wait(), timeout=step.pause_seconds
                    )
                    # If we get here, cancel was set
                    break
                except asyncio.TimeoutError:
                    pass  # Normal: timeout means we proceed
            else:
                await asyncio.sleep(step.pause_seconds)

        return {"scenario": self.scenario_id, "status": "complete"}


# ---------------------------------------------------------------------------
# Helper: pattern factory
# ---------------------------------------------------------------------------

def _make_pattern(
    pid: str,
    name: str,
    desc: str,
    trigger_type: str,
    trigger_value: str,
    actions: list[dict],
    ptype: PatternType = PatternType.USER_DEFINED,
    source: str = "",
) -> DetectedPattern:
    return DetectedPattern(
        pattern_id=pid,
        pattern_type=ptype,
        display_name=name,
        description=desc,
        frequency=10,
        confidence=0.95,
        trigger_conditions={"trigger_type": trigger_type, "value": trigger_value},
        action_sequence=[PatternAction(**a) for a in actions],
        approved=True,
        source_utterance=source,
    )


# ---------------------------------------------------------------------------
# Existing instant scenarios (kept for backwards compatibility)
# ---------------------------------------------------------------------------

class SummerHeatWave(Scenario):
    def __init__(self):
        super().__init__(
            "summer_heat_wave",
            "Summer Heat Wave",
            "Extreme heat (108°F), high grid demand (92%), elevated energy prices. "
            "Tests pre-cooling, battery management, and energy conservation."
        )

    async def execute(self, cancel_event=None) -> dict[str, Any]:
        await sim_overrides.set_weather(
            temperature_f=108, humidity=25, wind_speed_mph=8,
            description="extreme heat warning",
            alerts=["Excessive Heat Warning: 108°F expected"],
            forecast_high_f=112, forecast_low_f=88,
        )
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=92, lmp_price=150, system_load_mw=72000,
            operating_reserves_mw=2100, grid_alert_level="conservation",
        )
        await sim_overrides.set_battery_level(45)
        # Trigger threat assessment - it will automatically trigger orchestrator for HIGH/CRITICAL threats
        assessment = await threat_agent.run()
        # Give orchestrator time to process and show voice alert
        await asyncio.sleep(2)
        return {"scenario": self.scenario_id, "status": "active", "threat_level": assessment.threat_level.value if hasattr(assessment.threat_level, 'value') else str(assessment.threat_level)}


class WinterStorm(Scenario):
    def __init__(self):
        super().__init__(
            "winter_storm",
            "Winter Storm Uri",
            "Freezing temps (15°F), grid near collapse (97%), rolling outages imminent. "
            "Tests heating management, battery backup, and critical device prioritization."
        )

    async def execute(self, cancel_event=None) -> dict[str, Any]:
        await sim_overrides.set_weather(
            temperature_f=15, humidity=80, wind_speed_mph=25,
            description="winter storm warning with ice",
            alerts=["Winter Storm Warning", "Wind Chill Advisory: -5°F"],
            forecast_high_f=20, forecast_low_f=5,
        )
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=97, lmp_price=9000, system_load_mw=78000,
            operating_reserves_mw=800, grid_alert_level="eea3",
        )
        await sim_overrides.set_battery_level(30)
        # Trigger threat assessment - it will automatically trigger orchestrator for HIGH/CRITICAL threats
        assessment = await threat_agent.run()
        # Give orchestrator time to process and show voice alert
        await asyncio.sleep(2)
        return {"scenario": self.scenario_id, "status": "active", "threat_level": assessment.threat_level.value if hasattr(assessment.threat_level, 'value') else str(assessment.threat_level)}


class GridEmergency(Scenario):
    def __init__(self):
        super().__init__(
            "grid_emergency",
            "Grid Emergency",
            "ERCOT declares EEA3, rotating outages in progress. "
            "Tests maximum energy conservation and battery backup mode."
        )

    async def execute(self, cancel_event=None) -> dict[str, Any]:
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=99, lmp_price=5000, system_load_mw=80000,
            operating_reserves_mw=500, grid_alert_level="eea3",
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
        await sim_overrides.set_calendar_event(
            summary="Team Standup", starts_in_minutes=7,
            duration_minutes=30, location="Zoom",
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
        await sim_overrides.set_calendar_event(
            summary="Product Review Call", starts_in_minutes=-5,
            duration_minutes=45, location="Google Meet",
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

    async def execute(self, cancel_event=None) -> dict[str, Any]:
        await sim_overrides.clear_calendar_override()
        return {"scenario": self.scenario_id, "status": "active"}


# ===========================================================================
# TEMPORAL DEMO SCENARIOS
# ===========================================================================


class TexasGridCrisis(TemporalScenario):
    """Texas Summer Grid Crisis: 6 steps, ~90 seconds."""

    def __init__(self):
        super().__init__(
            "demo_texas_grid_crisis",
            "Texas Grid Crisis",
            "Texas summer, 107°F, ERCOT at 96%. System pre-cools 8 hours ahead, "
            "switches to battery backup at peak, saves $47. (90 sec demo)"
        )

        # Pre-seed patterns
        self._patterns_to_seed = [
            _make_pattern(
                "demo_p1", "User arrives home 5-6 PM, prefers 72°F",
                "Learned from 2 weeks of GPS + thermostat data: user arrives 5-6 PM and sets thermostat to 72°F.",
                "location", "arriving",
                [{"device_id": "thermostat_living", "action": "set_temperature", "parameters": {"temperature": 72}}],
                ptype=PatternType.ROUTINE,
                source="Learned from user behavior",
            ),
            _make_pattern(
                "demo_p2", "Never turn off fridge",
                "Global constraint: the fridge must never be turned off by automation.",
                "global", "always",
                [{"device_id": "plug_kitchen_fridge", "action": "off", "parameters": {}}],
                source="Never turn off the fridge",
            ),
            _make_pattern(
                "demo_p3", "Charge battery during solar peak",
                "Energy optimization: charge battery from solar panels during peak production (10AM-2PM).",
                "time", "10:00-14:00",
                [{"device_id": "battery_main", "action": "set_mode", "parameters": {"mode": "charge"}}],
                ptype=PatternType.ENERGY,
                source="Learned from solar production patterns",
            ),
        ]

        # Step 1: Morning Forecast Detection
        self.steps.append(TimelineStep(
            timestamp="6:00 AM",
            title="Threat Detection",
            description="Threat Agent analyzing weather forecast + ERCOT grid data...",
            actions=[self._step1_detect_threat],
            pause_seconds=10,
            metrics={},
        ))

        # Step 2: Pre-Cooling
        self.steps.append(TimelineStep(
            timestamp="6:15 AM",
            title="Agent Decision: Pre-Cooling Strategy",
            description="Orchestrator agent analyzing threat and deciding to pre-cool using cheap $0.08/kWh electricity...",
            actions=[self._step2_precool],
            pause_seconds=10,
            metrics={"electricity_rate": "$0.08/kWh", "strategy": "Pre-cool before peak"},
        ))

        # Step 3: Battery Charging
        self.steps.append(TimelineStep(
            timestamp="10:00 AM",
            title="Solar Battery Charging",
            description="Solar peak production. Charging battery from 45% to 95%...",
            actions=[self._step3_charge_battery],
            pause_seconds=10,
            metrics={"solar_production": "4.5 kW", "battery_target": "95%"},
        ))

        # Step 4: Peak Crisis
        self.steps.append(TimelineStep(
            timestamp="2:00 PM",
            title="Peak Demand Crisis",
            description="ERCOT peak demand! Grid at 98% capacity. LMP price: $250/MWh",
            actions=[self._step4_peak_crisis],
            pause_seconds=10,
            metrics={"grid_capacity": "98%", "lmp_price": "$250/MWh"},
        ))

        # Step 5: Battery Backup
        self.steps.append(TimelineStep(
            timestamp="2:05 PM",
            title="Agent Decision: Battery Backup Mode",
            description="Orchestrator agent responding to peak crisis by switching to battery backup and turning off non-essential devices.",
            actions=[self._step5_battery_backup],
            pause_seconds=10,
            metrics={"battery_mode": "discharge", "devices_off": "TV, Coffee Maker, Ambient Light"},
        ))

        # Step 6: Summary
        self.steps.append(TimelineStep(
            timestamp="5:00 PM",
            title="Crisis Resolved",
            description="User arrives home. Crisis avoided! Home comfortable at 72°F.",
            actions=[self._step6_summary],
            pause_seconds=20,
            metrics={
                "cost_savings": "$47.00",
                "energy_shifted": "18.2 kWh (80%)",
                "peak_demand_reduced": "3.4 kW",
                "battery_remaining": "68%",
                "home_temp": "72°F",
            },
        ))

    async def _step1_detect_threat(self):
        """Set weather + grid conditions and trigger threat assessment agent."""
        await sim_overrides.set_weather(
            temperature_f=107, humidity=20, wind_speed_mph=8,
            description="extreme heat warning",
            alerts=["Excessive Heat Warning: 107°F expected today"],
            forecast_high_f=112, forecast_low_f=88,
        )
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=96, lmp_price=180, system_load_mw=72000,
            operating_reserves_mw=2100, grid_alert_level="conservation",
        )
        await sim_overrides.set_battery_level(45)
        # Trigger threat agent - it will automatically trigger orchestrator for HIGH/CRITICAL threats
        await threat_agent.run()

    async def _step2_precool(self):
        """Wait for orchestrator to respond to threat (no hardcoded actions)."""
        # Orchestrator will have already responded to the threat from step 1
        # This step is just for narrative timing
        pass

    async def _step3_charge_battery(self):
        """Set solar generation conditions - agents will decide battery actions."""
        await sim_overrides.set_solar_generation(4500)
        await sim_overrides.set_battery_level(95)
        # Agents will decide to charge battery based on solar production

    async def _step4_peak_crisis(self):
        """Escalate grid conditions - agents will respond automatically."""
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=98, lmp_price=250, system_load_mw=76000,
            operating_reserves_mw=1200, grid_alert_level="conservation",
        )
        # Trigger threat agent again to reassess with new conditions
        await threat_agent.run()

    async def _step5_battery_backup(self):
        """Wait for orchestrator to respond to escalated threat (no hardcoded actions)."""
        # Orchestrator will have already responded to the escalated threat from step 4
        # This step is just for narrative timing
        pass

    async def _step6_summary(self):
        """User arrives home, play voice summary."""
        await sim_overrides.set_gps_location("home")
        from src.agents.voice import voice_agent
        await voice_agent.run(
            message=(
                "Grid crisis managed successfully. I pre-cooled your home at 6 AM using cheap electricity "
                "at 8 cents per kilowatt hour, and avoided peak rates of 25 cents per kilowatt hour from "
                "2 to 7 PM. I saved you about 47 dollars today. Your battery is at 68 percent and your "
                "home is a comfortable 72 degrees."
            ),
            require_permission=False,
        )


class WinterStormPrep(TemporalScenario):
    """Winter Storm Survival Prep: 5 steps, ~70 seconds."""

    def __init__(self):
        super().__init__(
            "demo_winter_storm",
            "Winter Storm Survival",
            "Dallas, Feb 2026. Storm Uri 2.0 forecast: 15°F, ice, grid collapse risk. "
            "System prepares home 18 hours ahead. (70 sec demo)"
        )

        # Pre-seed patterns
        self._patterns_to_seed = [
            _make_pattern(
                "demo_w1", "Storm prep: battery full charge",
                "When a winter storm is forecast, charge battery to 100% from grid before outage.",
                "global", "always",
                [{"device_id": "battery_main", "action": "set_mode", "parameters": {"mode": "charge"}}],
                ptype=PatternType.ENERGY,
                source="Charge battery before storms",
            ),
            _make_pattern(
                "demo_w2", "Pre-heat water heater before outages",
                "Heat water heater to maximum before a predicted outage to store thermal energy.",
                "global", "always",
                [{"device_id": "water_heater_main", "action": "boost", "parameters": {"temperature_f": 140}}],
                ptype=PatternType.ENERGY,
                source="Pre-heat water heater before storms",
            ),
            _make_pattern(
                "demo_w3", "Never turn off fridge",
                "Global constraint: the fridge must never be turned off by automation.",
                "global", "always",
                [{"device_id": "plug_kitchen_fridge", "action": "off", "parameters": {}}],
                source="Never turn off the fridge",
            ),
            _make_pattern(
                "demo_w4", "Lock doors during storms",
                "Security: automatically lock all doors when severe weather is detected.",
                "global", "always",
                [{"device_id": "lock_front_door", "action": "lock", "parameters": {}}],
                ptype=PatternType.USER_DEFINED,
                source="Lock doors during storms",
            ),
        ]

        # Step 1: Storm Warning
        self.steps.append(TimelineStep(
            timestamp="6:00 AM",
            title="Storm Warning Detected",
            description="Severe winter storm forecast: 15°F, ice, wind chill -5°F. Grid collapse risk.",
            actions=[self._step1_storm_warning],
            pause_seconds=10,
            metrics={"threat_level": "CRITICAL", "forecast": "15°F with ice"},
        ))

        # Step 2: Water Heater Pre-Heat
        self.steps.append(TimelineStep(
            timestamp="6:30 AM",
            title="Water Heater Pre-Heating",
            description="Boosting water heater to 140°F to store thermal energy (6.5 kWh).",
            actions=[self._step2_preheat],
            pause_seconds=10,
            metrics={"water_heater_target": "140°F", "thermal_energy": "6.5 kWh", "home_target": "74°F"},
        ))

        # Step 3: Battery Charge
        self.steps.append(TimelineStep(
            timestamp="7:00 AM",
            title="Battery Full Charge",
            description="Charging battery to 100% from grid. 13.5 kWh = 36 hours of critical loads.",
            actions=[self._step3_charge_battery],
            pause_seconds=10,
            metrics={"battery_target": "100%", "capacity": "13.5 kWh", "runtime": "36 hours critical loads", "charge_cost": "$10.80"},
        ))

        # Step 4: Lockdown Mode
        self.steps.append(TimelineStep(
            timestamp="8:00 PM",
            title="Lockdown Mode",
            description="Storm arriving. Survival lockdown: non-essential OFF, battery backup mode.",
            actions=[self._step4_lockdown],
            pause_seconds=10,
            metrics={"battery_mode": "backup", "active_devices": "Fridge, thermostats, one light per room"},
        ))

        # Step 5: Survival Mode
        self.steps.append(TimelineStep(
            timestamp="Day 2, 6:00 AM",
            title="Survival Mode Active",
            description="Grid still unstable. Battery at 72%. Home at 70°F.",
            actions=[self._step5_survival],
            pause_seconds=20,
            metrics={
                "battery_remaining": "72% (9.7 kWh)",
                "time_to_empty": "26 hours",
                "home_temp": "70°F",
                "water_heater": "Still 115°F",
                "grid_status": "OFFLINE",
            },
        ))

    async def _step1_storm_warning(self):
        """Set weather + grid conditions and trigger threat assessment agent."""
        await sim_overrides.set_weather(
            temperature_f=15, humidity=80, wind_speed_mph=25,
            description="winter storm warning with ice",
            alerts=["Winter Storm Warning", "Wind Chill Advisory: -5°F"],
            forecast_high_f=20, forecast_low_f=5,
        )
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=97, lmp_price=9000, system_load_mw=78000,
            operating_reserves_mw=800, grid_alert_level="eea3",
        )
        await sim_overrides.set_battery_level(55)
        # Trigger threat agent - it will automatically trigger orchestrator for HIGH/CRITICAL threats
        await threat_agent.run()

    async def _step2_preheat(self):
        """Wait for orchestrator to respond to threat (no hardcoded actions)."""
        # Orchestrator will have already responded to the threat from step 1
        # This step is just for narrative timing
        pass

    async def _step3_charge_battery(self):
        """Set battery level - agents will decide charging based on conditions."""
        await sim_overrides.set_battery_level(100)
        # Agents will decide to charge battery based on threat assessment

    async def _step4_lockdown(self):
        """Escalate weather conditions - agents will respond automatically."""
        # Weather worsens
        await sim_overrides.set_weather(
            temperature_f=18, humidity=85, wind_speed_mph=30,
            description="winter storm with ice and freezing rain",
            alerts=["Winter Storm Warning", "Ice Storm Warning"],
            forecast_high_f=22, forecast_low_f=8,
        )
        # Trigger threat agent again to reassess with worsened conditions
        await threat_agent.run()

    async def _step5_survival(self):
        # Simulate grid outage
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=100, lmp_price=9999, system_load_mw=80000,
            operating_reserves_mw=0, grid_alert_level="eea3",
        )
        await sim_overrides.set_battery_level(72)
        from src.agents.voice import voice_agent
        await voice_agent.run(
            message=(
                "Grid outage is ongoing. Your battery is at 72 percent with an estimated 26 more hours "
                "of power for critical loads. Home temperature is a comfortable 70 degrees. The water heater "
                "still has stored thermal energy at 115 degrees."
            ),
            require_permission=False,
        )


class SolarBatteryMaster(TemporalScenario):
    """Solar + Battery ROI Master: 7 steps, ~100 seconds."""

    def __init__(self):
        super().__init__(
            "demo_solar_battery",
            "Solar + Battery ROI",
            "24-hour energy arbitrage: discharge during peaks ($0.22/kWh), charge during "
            "valleys ($0.05/kWh). Reduces solar+battery payback from 10 to 6.2 years. (100 sec demo)"
        )

        # Pre-seed patterns
        self._patterns_to_seed = [
            _make_pattern(
                "demo_s1", "Discharge battery during price peaks",
                "Energy arbitrage: discharge battery to power home during high-price periods ($0.12-0.22/kWh).",
                "time", "06:00-07:00,17:00-20:00",
                [{"device_id": "battery_main", "action": "set_mode", "parameters": {"mode": "discharge"}}],
                ptype=PatternType.ENERGY,
                source="Learned from ERCOT price patterns",
            ),
            _make_pattern(
                "demo_s2", "Charge from solar during production peak",
                "Renewable priority: charge battery from solar panels during peak production (10AM-2PM).",
                "time", "10:00-14:00",
                [{"device_id": "battery_main", "action": "set_mode", "parameters": {"mode": "charge"}}],
                ptype=PatternType.ENERGY,
                source="Learned from solar production patterns",
            ),
            _make_pattern(
                "demo_s3", "Recharge battery overnight during price valleys",
                "Grid arbitrage: buy cheap electricity ($0.05/kWh) overnight to charge battery for next day.",
                "time", "23:00-05:00",
                [{"device_id": "battery_main", "action": "set_mode", "parameters": {"mode": "charge"}}],
                ptype=PatternType.ENERGY,
                source="Learned from ERCOT overnight pricing",
            ),
            _make_pattern(
                "demo_s4", "User evening load pattern",
                "Learned: user evening consumption (5-8 PM) averages 3.2 kW (cooking, TV, lights).",
                "time", "17:00-20:00",
                [
                    {"device_id": "light_living_main", "action": "on", "parameters": {"brightness": 80}},
                    {"device_id": "plug_living_tv", "action": "on", "parameters": {}},
                ],
                ptype=PatternType.ROUTINE,
                source="Learned from device usage patterns",
            ),
        ]

        # Step 1: Morning Analysis
        self.steps.append(TimelineStep(
            timestamp="5:00 AM",
            title="Price Forecast Analysis",
            description="Analyzing ERCOT 24-hour pricing. Identifying peaks ($0.12-0.22) and valleys ($0.05).",
            actions=[self._step1_analysis],
            pause_seconds=10,
            metrics={
                "morning_peak": "$0.12/kWh (6-7 AM)",
                "solar_cheap": "$0.06/kWh (10AM-2PM)",
                "evening_peak": "$0.22/kWh (5-8 PM)",
                "overnight_valley": "$0.05/kWh (11PM-5AM)",
                "strategy": "Discharge peaks, charge valleys",
            },
        ))

        # Step 2: Morning Peak Discharge
        self.steps.append(TimelineStep(
            timestamp="6:00 AM",
            title="Morning Peak Discharge",
            description="Morning price spike ($0.12/kWh). Powering home from battery instead of grid.",
            actions=[self._step2_morning_discharge],
            pause_seconds=10,
            metrics={
                "grid_price": "$0.12/kWh",
                "battery_mode": "discharge",
                "battery_level": "80% → 65%",
                "savings_this_hour": "$0.38",
            },
        ))

        # Step 3: Solar Charging
        self.steps.append(TimelineStep(
            timestamp="10:00 AM",
            title="Solar Peak Charging",
            description="Solar production peak: 4.8 kW. Charging battery with free solar + cheap grid.",
            actions=[self._step3_solar_charge],
            pause_seconds=15,
            metrics={
                "solar_production": "4.8 kW",
                "home_consumption": "1.2 kW",
                "surplus_to_battery": "3.6 kW",
                "battery_level": "65% → 95%",
                "grid_price": "$0.06/kWh",
            },
        ))

        # Step 4: Hold Strategy
        self.steps.append(TimelineStep(
            timestamp="2:00 PM",
            title="Afternoon Hold Strategy",
            description="Grid price moderate ($0.08/kWh). Holding battery for $0.22/kWh evening peak.",
            actions=[self._step4_hold],
            pause_seconds=10,
            metrics={
                "grid_price": "$0.08/kWh",
                "battery_mode": "HOLD",
                "battery_level": "95%",
                "strategy": "Waiting for evening peak to maximize profit",
            },
        ))

        # Step 5: Evening Peak Discharge
        self.steps.append(TimelineStep(
            timestamp="5:00 PM",
            title="Evening Peak Discharge",
            description="Evening peak! Grid at $0.22/kWh. Discharging battery. Zero grid consumption.",
            actions=[self._step5_evening_discharge],
            pause_seconds=10,
            metrics={
                "grid_price": "$0.22/kWh (PEAK)",
                "battery_mode": "discharge",
                "battery_level": "95% → 45%",
                "home_load": "3.2 kW (all from battery)",
                "savings_3_hours": "$2.11",
            },
        ))

        # Step 6: Night Recharge
        self.steps.append(TimelineStep(
            timestamp="11:00 PM",
            title="Overnight Cheap Recharge",
            description="Overnight valley: grid at $0.05/kWh. Recharging battery for tomorrow's peaks.",
            actions=[self._step6_night_recharge],
            pause_seconds=10,
            metrics={
                "grid_price": "$0.05/kWh (CHEAPEST)",
                "battery_mode": "charge",
                "battery_level": "45% → 85%",
                "recharge_cost": "$0.27",
                "arbitrage": "Sold at $0.18 avg, bought at $0.05",
            },
        ))

        # Step 7: Summary
        self.steps.append(TimelineStep(
            timestamp="Next Day, 5:00 AM",
            title="Daily ROI Summary",
            description="24-hour cycle complete! Smart arbitrage saved $4.30. Payback: 6.2 years vs 10.",
            actions=[self._step7_summary],
            pause_seconds=20,
            metrics={
                "daily_savings": "$4.30",
                "arbitrage_profit": "$1.20",
                "kwh_shifted": "13.6 kWh",
                "peak_demand_avoided": "100%",
                "monthly_savings": "$36",
                "annual_savings": "$432",
                "roi_years": "6.2 (vs 10 without AI)",
            },
        ))

    async def _step1_analysis(self):
        """Set initial conditions: moderate grid, battery at 80%."""
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=65, lmp_price=50, system_load_mw=45000,
            operating_reserves_mw=4000, grid_alert_level="normal",
        )
        await sim_overrides.set_battery_level(80)
        await sim_overrides.set_solar_generation(0)  # Pre-dawn

    async def _step2_morning_discharge(self):
        """Set grid conditions for morning peak - patterns will trigger battery discharge."""
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=72, lmp_price=120, system_load_mw=55000,
            operating_reserves_mw=3500, grid_alert_level="normal",
        )
        await sim_overrides.set_battery_level(65)
        # Seeded patterns will trigger battery discharge during price peaks

    async def _step3_solar_charge(self):
        """Set solar generation and grid conditions - patterns will trigger battery charging."""
        await sim_overrides.set_solar_generation(4800)
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=58, lmp_price=60, system_load_mw=42000,
            operating_reserves_mw=5000, grid_alert_level="normal",
        )
        await sim_overrides.set_battery_level(95)
        # Seeded patterns will trigger battery charge from solar during peak production

    async def _step4_hold(self):
        """Set moderate price conditions - agents/patterns will hold battery."""
        await sim_overrides.set_solar_generation(2000)
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=68, lmp_price=80, system_load_mw=50000,
            operating_reserves_mw=4000, grid_alert_level="normal",
        )
        # Agents/patterns will decide to hold battery for evening peak

    async def _step5_evening_discharge(self):
        """Set evening peak conditions - patterns will trigger battery discharge."""
        await sim_overrides.set_solar_generation(0)
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=88, lmp_price=220, system_load_mw=68000,
            operating_reserves_mw=2500, grid_alert_level="conservation",
        )
        await sim_overrides.set_battery_level(45)
        # Seeded patterns will trigger battery discharge during evening price peak
        # User evening load pattern will trigger lights/TV via pattern

    async def _step6_night_recharge(self):
        """Set overnight cheap rates - patterns will trigger battery charging."""
        await sim_overrides.set_grid_conditions(
            load_capacity_pct=42, lmp_price=50, system_load_mw=35000,
            operating_reserves_mw=6000, grid_alert_level="normal",
        )
        await sim_overrides.set_battery_level(85)
        # Seeded patterns will trigger battery charge during overnight price valley

    async def _step7_summary(self):
        """Play voice summary with ROI info."""
        from src.agents.voice import voice_agent
        await voice_agent.run(
            message=(
                "Daily energy optimization complete. Yesterday I saved you 4 dollars and 30 cents "
                "through smart energy arbitrage. I discharged 8.2 kilowatt hours during peak prices "
                "averaging 18 cents per kilowatt hour, and recharged during the overnight valley at "
                "just 5 cents per kilowatt hour. Your net arbitrage profit is 1 dollar 20 cents. "
                "At this rate, your solar and battery system will pay for itself in 6.2 years instead "
                "of the typical 10 years. That is 432 dollars in annual savings."
            ),
            require_permission=False,
        )


# ===========================================================================
# Registry
# ===========================================================================

SCENARIOS: dict[str, Scenario] = {
    # Existing instant scenarios
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
    # Temporal demo scenarios
    "demo_texas_grid_crisis": TexasGridCrisis(),
    "demo_winter_storm": WinterStormPrep(),
    "demo_solar_battery": SolarBatteryMaster(),
}


def get_scenario_list() -> list[dict[str, str]]:
    """Get list of all available scenarios."""
    result = []
    for s in SCENARIOS.values():
        entry: dict[str, Any] = {
            "id": s.scenario_id,
            "name": s.name,
            "description": s.description,
        }
        if isinstance(s, TemporalScenario):
            entry["temporal"] = True
            entry["total_steps"] = len(s.steps)
        else:
            entry["temporal"] = False
        result.append(entry)
    return result
