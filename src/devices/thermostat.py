"""Thermostat device simulator."""

import random
from typing import Any

from src.devices.base import BaseDevice
from src.models.device import ThermostatMode


class ThermostatDevice(BaseDevice):
    """Simulated smart thermostat with temperature control and modes."""

    MIN_TEMP_F = 60
    MAX_TEMP_F = 85

    def __init__(self, config):
        super().__init__(config)
        self._state.properties = {
            "current_temp_f": 72.0,
            "target_temp_f": 72.0,
            "mode": ThermostatMode.AUTO.value,
            "fan": "auto",
            "humidity_pct": 45.0,
        }
        self._state.power = True  # Thermostat is always "on"

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "set_temperature":
                temp = parameters.get("temperature", 72)
                if temp < self.MIN_TEMP_F or temp > self.MAX_TEMP_F:
                    return {
                        "success": False,
                        "error": f"Temperature must be between {self.MIN_TEMP_F}F and {self.MAX_TEMP_F}F",
                    }
                self._state.properties["target_temp_f"] = float(temp)
                return {"success": True, "target_temp_f": temp}

            case "set_mode":
                mode = parameters.get("mode", "auto")
                try:
                    valid_mode = ThermostatMode(mode)
                    self._state.properties["mode"] = valid_mode.value
                    if valid_mode == ThermostatMode.OFF:
                        self._state.power = False
                    else:
                        self._state.power = True
                    return {"success": True, "mode": valid_mode.value}
                except ValueError:
                    return {"success": False, "error": f"Invalid mode: {mode}"}

            case "eco_mode":
                self._state.properties["mode"] = ThermostatMode.ECO.value
                # ECO mode adjusts target by 3 degrees toward energy savings
                current = self._state.properties["target_temp_f"]
                if self._state.properties.get("mode") == ThermostatMode.COOL.value:
                    self._state.properties["target_temp_f"] = min(current + 3, self.MAX_TEMP_F)
                else:
                    self._state.properties["target_temp_f"] = max(current - 3, self.MIN_TEMP_F)
                return {
                    "success": True,
                    "mode": "eco",
                    "target_temp_f": self._state.properties["target_temp_f"],
                }

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _update_energy_usage(self) -> None:
        """Simulate energy based on difference between current and target temp."""
        mode = self._state.properties.get("mode", "auto")
        if mode == ThermostatMode.OFF.value or not self._state.power:
            self._state.current_watts = self._state.energy_profile.idle_watts
            return

        current = self._state.properties.get("current_temp_f", 72)
        target = self._state.properties.get("target_temp_f", 72)
        diff = abs(current - target)

        if diff < 0.5:
            # At target, minimal power
            self._state.current_watts = self._state.energy_profile.idle_watts
        else:
            # Scale power by temperature difference
            scale = min(diff / 10.0, 1.0)
            self._state.current_watts = (
                self._state.energy_profile.idle_watts
                + (self._state.energy_profile.active_watts - self._state.energy_profile.idle_watts)
                * scale
            )

    def _get_telemetry(self) -> dict[str, Any] | None:
        """Simulate gradual temperature changes toward target."""
        current = self._state.properties.get("current_temp_f", 72)
        target = self._state.properties.get("target_temp_f", 72)

        # Slowly move current temp toward target
        if abs(current - target) > 0.1:
            direction = 1 if target > current else -1
            change = direction * random.uniform(0.1, 0.5)
            self._state.properties["current_temp_f"] = round(current + change, 1)

        # Slight humidity variation
        humidity = self._state.properties.get("humidity_pct", 45)
        self._state.properties["humidity_pct"] = round(
            humidity + random.uniform(-0.5, 0.5), 1
        )

        base = super()._get_telemetry() or {}
        base.update({
            "current_temp_f": self._state.properties["current_temp_f"],
            "target_temp_f": self._state.properties["target_temp_f"],
            "mode": self._state.properties["mode"],
            "humidity_pct": self._state.properties["humidity_pct"],
        })
        return base
