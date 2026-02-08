"""Simulation engine -- orchestrates overrides, scenarios, and time control."""

import logging
from typing import Any

from src.simulation.overrides import sim_overrides
from src.simulation.scenarios import SCENARIOS, get_scenario_list
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)


class SimulationEngine:
    """Central engine for simulation control."""

    def __init__(self):
        self._time_multiplier: float = 1.0
        self._active_scenario: str | None = None

    @property
    def time_multiplier(self) -> float:
        return self._time_multiplier

    @property
    def active_scenario(self) -> str | None:
        return self._active_scenario

    async def run_scenario(self, scenario_id: str) -> dict[str, Any]:
        """Execute a pre-built scenario."""
        scenario = SCENARIOS.get(scenario_id)
        if not scenario:
            return {"success": False, "error": f"Unknown scenario: {scenario_id}"}

        # Clear previous overrides
        await sim_overrides.clear_all()

        logger.info(f"Running scenario: {scenario.name}")
        self._active_scenario = scenario_id

        result = await scenario.execute()

        await ws_manager.broadcast("scenario_active", {
            "scenario_id": scenario_id,
            "name": scenario.name,
            "description": scenario.description,
        })

        return {"success": True, **result}

    async def stop_scenario(self) -> dict[str, Any]:
        """Stop the current scenario and clear overrides."""
        await sim_overrides.clear_all()
        self._active_scenario = None
        await ws_manager.broadcast("scenario_stopped", {})
        return {"success": True}

    def set_time_multiplier(self, multiplier: float) -> dict[str, Any]:
        """Set time acceleration multiplier."""
        self._time_multiplier = max(1.0, min(60.0, multiplier))
        logger.info(f"Time multiplier: {self._time_multiplier}x")
        return {"time_multiplier": self._time_multiplier}

    def get_status(self) -> dict[str, Any]:
        """Get current simulation status."""
        return {
            "time_multiplier": self._time_multiplier,
            "active_scenario": self._active_scenario,
            "active_overrides": sim_overrides.active,
            "available_scenarios": get_scenario_list(),
        }


# Singleton
sim_engine = SimulationEngine()
