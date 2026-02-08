"""Light device simulator."""

from typing import Any

from src.devices.base import BaseDevice


class LightDevice(BaseDevice):
    """Simulated smart light with dimming and color control."""

    def __init__(self, config):
        super().__init__(config)
        self._state.properties = {
            "brightness": 0,
            "color": {"r": 255, "g": 255, "b": 255},
            "color_temp_k": 4000,
        }

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "on":
                self._state.power = True
                brightness = parameters.get("brightness", 100)
                self._state.properties["brightness"] = max(1, min(100, brightness))
                return {"success": True, "state": "on", "brightness": self._state.properties["brightness"]}

            case "off":
                self._state.power = False
                self._state.properties["brightness"] = 0
                return {"success": True, "state": "off"}

            case "dim":
                level = parameters.get("brightness", 50)
                level = max(0, min(100, level))
                self._state.properties["brightness"] = level
                self._state.power = level > 0
                return {"success": True, "brightness": level}

            case "color":
                r = parameters.get("r", 255)
                g = parameters.get("g", 255)
                b = parameters.get("b", 255)
                self._state.properties["color"] = {
                    "r": max(0, min(255, r)),
                    "g": max(0, min(255, g)),
                    "b": max(0, min(255, b)),
                }
                if not self._state.power:
                    self._state.power = True
                    self._state.properties["brightness"] = 100
                return {"success": True, "color": self._state.properties["color"]}

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _update_energy_usage(self) -> None:
        """Scale energy usage by brightness level."""
        if self._state.power:
            brightness_pct = self._state.properties.get("brightness", 100) / 100.0
            self._state.current_watts = (
                self._state.energy_profile.idle_watts
                + (self._state.energy_profile.active_watts - self._state.energy_profile.idle_watts)
                * brightness_pct
            )
        else:
            self._state.current_watts = self._state.energy_profile.idle_watts
