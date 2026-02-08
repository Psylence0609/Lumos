"""Simulation engine -- orchestrates overrides, scenarios, and time control."""

import asyncio
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
        self._scenario_task: asyncio.Task | None = None
        self._cancel_event: asyncio.Event = asyncio.Event()

    @property
    def time_multiplier(self) -> float:
        return self._time_multiplier

    @property
    def active_scenario(self) -> str | None:
        return self._active_scenario

    @property
    def cancel_event(self) -> asyncio.Event:
        return self._cancel_event

    async def run_scenario(self, scenario_id: str) -> dict[str, Any]:
        """Execute a pre-built scenario."""
        scenario = SCENARIOS.get(scenario_id)
        if not scenario:
            return {"success": False, "error": f"Unknown scenario: {scenario_id}"}

        # Cancel any running scenario
        if self._scenario_task and not self._scenario_task.done():
            await self.stop_scenario()

        # Clear previous overrides
        await sim_overrides.clear_all()
        self._cancel_event.clear()

        logger.info(f"Running scenario: {scenario.name}")
        self._active_scenario = scenario_id

        # Check if this is a temporal scenario (has steps attribute)
        if hasattr(scenario, "steps"):
            # Run temporal scenarios as background tasks
            self._scenario_task = asyncio.create_task(
                self._run_temporal(scenario)
            )
            await ws_manager.broadcast("scenario_active", {
                "scenario_id": scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "temporal": True,
                "total_steps": len(scenario.steps),
            })
            return {"success": True, "scenario": scenario_id, "status": "running", "temporal": True}
        else:
            # Instant scenarios run directly
            result = await scenario.execute()
            await ws_manager.broadcast("scenario_active", {
                "scenario_id": scenario_id,
                "name": scenario.name,
                "description": scenario.description,
                "temporal": False,
            })
            return {"success": True, **result}

    async def _run_temporal(self, scenario) -> None:
        """Execute a temporal scenario step by step as a background task."""
        try:
            await scenario.execute(self._cancel_event)
        except asyncio.CancelledError:
            logger.info(f"Temporal scenario {scenario.scenario_id} cancelled")
        except Exception:
            logger.exception(f"Temporal scenario {scenario.scenario_id} failed")
        finally:
            self._active_scenario = None
            await ws_manager.broadcast("scenario_complete", {
                "scenario_id": scenario.scenario_id,
            })

    async def stop_scenario(self) -> dict[str, Any]:
        """Stop the current scenario and clear overrides."""
        # Signal cancel to temporal scenarios
        self._cancel_event.set()

        if self._scenario_task and not self._scenario_task.done():
            self._scenario_task.cancel()
            try:
                await self._scenario_task
            except (asyncio.CancelledError, Exception):
                pass

        await sim_overrides.clear_all()
        self._active_scenario = None
        self._scenario_task = None
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
