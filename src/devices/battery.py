"""Battery and solar system device simulator."""

import random
from datetime import datetime
from typing import Any

from src.devices.base import BaseDevice
from src.models.device import BatteryMode


class BatteryDevice(BaseDevice):
    """Simulated home battery with solar panel integration."""

    def __init__(self, config):
        super().__init__(config)
        capacity_kwh = config.battery_capacity_kwh or 13.5
        solar_watts = config.solar_panel_watts or 5000

        self._state.properties = {
            "battery_pct": 75.0,
            "battery_kwh": capacity_kwh * 0.75,
            "capacity_kwh": capacity_kwh,
            "mode": BatteryMode.AUTO.value,
            "solar_generation_watts": 0.0,
            "solar_panel_capacity_watts": solar_watts,
            "grid_import_watts": 0.0,
            "grid_export_watts": 0.0,
            "home_consumption_watts": 0.0,
            "charging": False,
            "discharging": False,
        }
        self._state.power = True  # Always on

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "set_mode":
                mode = parameters.get("mode", "auto")
                try:
                    valid_mode = BatteryMode(mode)
                    self._state.properties["mode"] = valid_mode.value
                    return {"success": True, "mode": valid_mode.value}
                except ValueError:
                    return {"success": False, "error": f"Invalid mode: {mode}"}

            case "charge":
                self._state.properties["charging"] = True
                self._state.properties["discharging"] = False
                self._state.properties["mode"] = BatteryMode.CHARGE.value
                return {"success": True, "charging": True}

            case "discharge":
                self._state.properties["charging"] = False
                self._state.properties["discharging"] = True
                self._state.properties["mode"] = BatteryMode.DISCHARGE.value
                return {"success": True, "discharging": True}

            case "status":
                return {
                    "success": True,
                    "battery_pct": self._state.properties["battery_pct"],
                    "mode": self._state.properties["mode"],
                    "solar_generation_watts": self._state.properties["solar_generation_watts"],
                }

            case "set_battery_level":
                # Simulation override
                level = parameters.get("level", 75)
                level = max(0, min(100, level))
                capacity = self._state.properties["capacity_kwh"]
                self._state.properties["battery_pct"] = float(level)
                self._state.properties["battery_kwh"] = capacity * level / 100.0
                return {"success": True, "battery_pct": level}

            case "set_solar_generation":
                # Simulation override
                watts = parameters.get("watts", 0)
                self._state.properties["solar_generation_watts"] = max(0, float(watts))
                return {"success": True, "solar_generation_watts": watts}

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _get_telemetry(self) -> dict[str, Any] | None:
        """Simulate solar generation based on time of day and battery dynamics."""
        now = datetime.now()
        hour = now.hour

        # Simulate solar generation curve (peaks at noon)
        solar_capacity = self._state.properties["solar_panel_capacity_watts"]
        if 6 <= hour <= 20:
            # Bell curve peaking at 13:00
            solar_factor = max(0, 1 - ((hour - 13) / 7) ** 2)
            solar_factor *= random.uniform(0.8, 1.0)  # Cloud variation
            self._state.properties["solar_generation_watts"] = round(
                solar_capacity * solar_factor, 1
            )
        else:
            self._state.properties["solar_generation_watts"] = 0.0

        # Simulate battery charge/discharge
        mode = self._state.properties["mode"]
        battery_pct = self._state.properties["battery_pct"]
        capacity = self._state.properties["capacity_kwh"]
        solar_w = self._state.properties["solar_generation_watts"]

        if mode == BatteryMode.CHARGE.value or (
            mode == BatteryMode.AUTO.value and solar_w > 500
        ):
            # Charging from solar
            charge_rate = min(solar_w, 3000) / 1000  # kW
            charge_kwh = charge_rate * (30 / 3600)  # 30 second interval
            new_kwh = min(
                self._state.properties["battery_kwh"] + charge_kwh, capacity
            )
            self._state.properties["battery_kwh"] = round(new_kwh, 3)
            self._state.properties["charging"] = True
            self._state.properties["discharging"] = False
        elif mode == BatteryMode.DISCHARGE.value or (
            mode == BatteryMode.AUTO.value and solar_w < 100
        ):
            # Discharging to home
            discharge_rate = 1.5  # kW
            discharge_kwh = discharge_rate * (30 / 3600)
            new_kwh = max(
                self._state.properties["battery_kwh"] - discharge_kwh, 0
            )
            self._state.properties["battery_kwh"] = round(new_kwh, 3)
            self._state.properties["charging"] = False
            self._state.properties["discharging"] = True

        self._state.properties["battery_pct"] = round(
            (self._state.properties["battery_kwh"] / capacity) * 100, 1
        )

        base = super()._get_telemetry() or {}
        base.update({
            "battery_pct": self._state.properties["battery_pct"],
            "battery_kwh": self._state.properties["battery_kwh"],
            "solar_generation_watts": self._state.properties["solar_generation_watts"],
            "mode": self._state.properties["mode"],
            "charging": self._state.properties["charging"],
            "discharging": self._state.properties["discharging"],
        })
        return base
