"""Coffee maker device simulator."""

import asyncio
from typing import Any

from src.devices.base import BaseDevice


class CoffeeMakerDevice(BaseDevice):
    """Simulated smart coffee maker."""

    def __init__(self, config):
        super().__init__(config)
        self._state.properties = {
            "brewing": False,
            "keep_warm": False,
            "water_level_pct": 80.0,
            "brew_strength": "medium",  # light, medium, strong
            "cups_remaining": 8,
        }
        self._brew_task: asyncio.Task | None = None

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "on":
                # Turn on / enter standby without brewing
                self._state.power = True
                return {"success": True, "state": "standby"}

            case "brew":
                if self._state.properties["brewing"]:
                    return {"success": False, "error": "Already brewing"}
                if self._state.properties["water_level_pct"] < 10:
                    return {"success": False, "error": "Water level too low"}

                strength = parameters.get("strength", "medium")
                if strength in ("light", "medium", "strong"):
                    self._state.properties["brew_strength"] = strength

                self._state.power = True
                self._state.properties["brewing"] = True
                self._brew_task = asyncio.create_task(self._brew_cycle())
                return {"success": True, "brewing": True, "strength": strength}

            case "off":
                self._state.power = False
                self._state.properties["brewing"] = False
                self._state.properties["keep_warm"] = False
                if self._brew_task and not self._brew_task.done():
                    self._brew_task.cancel()
                return {"success": True, "state": "off"}

            case "keep_warm":
                enabled = parameters.get("enabled", True)
                self._state.properties["keep_warm"] = enabled
                if enabled:
                    self._state.power = True
                return {"success": True, "keep_warm": enabled}

            case "schedule":
                # Scheduling is handled by the pattern detector / orchestrator
                return {"success": True, "scheduled": True}

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    async def _brew_cycle(self) -> None:
        """Simulate a brew cycle (takes ~60 seconds in sim, scaled)."""
        try:
            await asyncio.sleep(5)  # 5 seconds to simulate brewing
            self._state.properties["brewing"] = False
            self._state.properties["keep_warm"] = True
            water = self._state.properties["water_level_pct"]
            self._state.properties["water_level_pct"] = max(0, water - 15)
            cups = self._state.properties["cups_remaining"]
            self._state.properties["cups_remaining"] = max(0, cups - 1)
            await self._publish_state()
        except asyncio.CancelledError:
            self._state.properties["brewing"] = False

    def _update_energy_usage(self) -> None:
        if self._state.properties.get("brewing"):
            self._state.current_watts = self._state.energy_profile.active_watts
        elif self._state.properties.get("keep_warm"):
            self._state.current_watts = self._state.energy_profile.active_watts * 0.1
        elif self._state.power:
            self._state.current_watts = self._state.energy_profile.idle_watts
        else:
            self._state.current_watts = 0.0
