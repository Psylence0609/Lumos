"""Water heater device simulator with thermal energy storage."""

import random
from datetime import datetime
from typing import Any

from src.devices.base import BaseDevice


class WaterHeaterDevice(BaseDevice):
    """Simulated smart water heater with temperature control and thermal storage."""

    def __init__(self, config):
        super().__init__(config)
        self._state.properties = {
            "temperature_f": 120.0,
            "target_temperature_f": 120.0,
            "heating": False,
            "mode": "normal",  # normal, boost, standby, off
            "tank_gallons": 50,
            "thermal_kwh": 4.2,  # stored thermal energy
        }
        self._state.power = True

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "heat" | "boost":
                target = parameters.get("temperature_f", 140.0)
                target = max(100, min(160, target))
                self._state.properties["target_temperature_f"] = target
                self._state.properties["heating"] = True
                self._state.properties["mode"] = "boost" if action == "boost" else "normal"
                return {"success": True, "target_temperature_f": target, "mode": self._state.properties["mode"]}

            case "set_temperature":
                target = parameters.get("temperature_f", 120.0)
                target = max(100, min(160, target))
                self._state.properties["target_temperature_f"] = target
                self._state.properties["heating"] = self._state.properties["temperature_f"] < target
                return {"success": True, "target_temperature_f": target}

            case "standby":
                self._state.properties["heating"] = False
                self._state.properties["mode"] = "standby"
                return {"success": True, "mode": "standby"}

            case "off":
                self._state.properties["heating"] = False
                self._state.properties["mode"] = "off"
                self._state.power = False
                return {"success": True, "mode": "off"}

            case "on":
                self._state.power = True
                self._state.properties["mode"] = "normal"
                return {"success": True, "mode": "normal"}

            case "status":
                return {
                    "success": True,
                    "temperature_f": self._state.properties["temperature_f"],
                    "target_temperature_f": self._state.properties["target_temperature_f"],
                    "heating": self._state.properties["heating"],
                    "mode": self._state.properties["mode"],
                    "thermal_kwh": self._state.properties["thermal_kwh"],
                }

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _get_telemetry(self) -> dict[str, Any] | None:
        """Simulate water heater thermal dynamics."""
        props = self._state.properties
        current_temp = props["temperature_f"]
        target_temp = props["target_temperature_f"]

        if props["heating"] and current_temp < target_temp:
            # Heating: ~1°F per 30 seconds for a 4500W heater on 50 gal
            heat_rate = random.uniform(0.8, 1.2)
            props["temperature_f"] = min(current_temp + heat_rate, target_temp)
            if props["temperature_f"] >= target_temp:
                props["heating"] = False
        elif props["mode"] != "off":
            # Natural heat loss: ~0.1°F per 30 seconds
            loss = random.uniform(0.05, 0.15)
            props["temperature_f"] = max(current_temp - loss, 70.0)

        # Calculate stored thermal energy (kWh)
        # Q = m * c * dT; 50 gal water, specific heat ~ 8.34 BTU/(gal·°F)
        delta_t = props["temperature_f"] - 70.0  # above ambient
        props["thermal_kwh"] = round((50 * 8.34 * delta_t) / 3412.0, 2)

        base = super()._get_telemetry() or {}
        base.update({
            "temperature_f": round(props["temperature_f"], 1),
            "target_temperature_f": props["target_temperature_f"],
            "heating": props["heating"],
            "mode": props["mode"],
            "thermal_kwh": props["thermal_kwh"],
        })
        return base
