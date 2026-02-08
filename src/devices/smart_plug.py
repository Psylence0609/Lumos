"""Smart plug device simulator."""

import random
from typing import Any

from src.devices.base import BaseDevice


class SmartPlugDevice(BaseDevice):
    """Simulated smart plug with energy monitoring."""

    def __init__(self, config):
        super().__init__(config)
        self._state.properties = {
            "relay_on": False,
            "total_kwh_today": 0.0,
            "voltage": 120.0,
            "current_amps": 0.0,
        }

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "on":
                self._state.power = True
                self._state.properties["relay_on"] = True
                return {"success": True, "relay_on": True}

            case "off":
                self._state.power = False
                self._state.properties["relay_on"] = False
                self._state.properties["current_amps"] = 0.0
                return {"success": True, "relay_on": False}

            case "monitor":
                return {
                    "success": True,
                    "relay_on": self._state.properties["relay_on"],
                    "current_watts": self._state.current_watts,
                    "total_kwh_today": self._state.properties["total_kwh_today"],
                    "voltage": self._state.properties["voltage"],
                    "current_amps": self._state.properties["current_amps"],
                }

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _update_energy_usage(self) -> None:
        if self._state.power and self._state.properties.get("relay_on"):
            # Simulate varying load
            base_watts = self._state.energy_profile.active_watts
            variation = random.uniform(0.9, 1.1)
            self._state.current_watts = round(base_watts * variation, 1)
            self._state.properties["current_amps"] = round(
                self._state.current_watts / 120.0, 2
            )
        else:
            self._state.current_watts = self._state.energy_profile.idle_watts
            self._state.properties["current_amps"] = 0.0

    def _get_telemetry(self) -> dict[str, Any] | None:
        """Track energy consumption."""
        if self._state.properties.get("relay_on"):
            # Accumulate kWh (30 second intervals)
            kwh_increment = self._state.current_watts * (30 / 3600) / 1000
            self._state.properties["total_kwh_today"] = round(
                self._state.properties["total_kwh_today"] + kwh_increment, 4
            )

        base = super()._get_telemetry() or {}
        base.update({
            "relay_on": self._state.properties["relay_on"],
            "total_kwh_today": self._state.properties["total_kwh_today"],
            "voltage": self._state.properties["voltage"],
            "current_amps": self._state.properties["current_amps"],
        })
        return base
