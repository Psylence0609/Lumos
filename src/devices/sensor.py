"""Sensor device simulator (motion, temperature)."""

import random
from datetime import datetime
from typing import Any

from src.devices.base import BaseDevice


class SensorDevice(BaseDevice):
    """Simulated sensor (motion or temperature)."""

    def __init__(self, config):
        super().__init__(config)
        sensor_type = config.sensor_type or "temperature"
        self._sensor_type = sensor_type
        self._state.power = True  # Sensors are always on

        if sensor_type == "motion":
            self._state.properties = {
                "sensor_type": "motion",
                "motion_detected": False,
                "last_motion": None,
                "sensitivity": "medium",
            }
        elif sensor_type == "temperature":
            self._state.properties = {
                "sensor_type": "temperature",
                "temperature_f": 72.0,
                "humidity_pct": 45.0,
            }

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "read":
                return {"success": True, "properties": self._state.properties}

            case "detect":
                # Simulation: trigger a motion event
                self._state.properties["motion_detected"] = True
                self._state.properties["last_motion"] = datetime.now().isoformat()
                return {"success": True, "motion_detected": True}

            case "clear":
                if self._sensor_type == "motion":
                    self._state.properties["motion_detected"] = False
                return {"success": True}

            case "set_temperature":
                # Simulation override
                temp = parameters.get("temperature", 72)
                self._state.properties["temperature_f"] = float(temp)
                return {"success": True, "temperature_f": temp}

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _get_telemetry(self) -> dict[str, Any] | None:
        """Simulate sensor readings with natural variation."""
        if self._sensor_type == "temperature":
            temp = self._state.properties.get("temperature_f", 72.0)
            # Small random drift
            self._state.properties["temperature_f"] = round(
                temp + random.uniform(-0.3, 0.3), 1
            )
            humidity = self._state.properties.get("humidity_pct", 45.0)
            self._state.properties["humidity_pct"] = round(
                max(20, min(80, humidity + random.uniform(-0.5, 0.5))), 1
            )
        elif self._sensor_type == "motion":
            # Randomly clear motion after some time
            if self._state.properties.get("motion_detected"):
                if random.random() < 0.3:  # 30% chance to clear each cycle
                    self._state.properties["motion_detected"] = False

        base = super()._get_telemetry() or {}
        base.update(self._state.properties)
        return base
