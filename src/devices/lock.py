"""Smart lock device simulator."""

from typing import Any

from src.devices.base import BaseDevice


class LockDevice(BaseDevice):
    """Simulated smart lock."""

    def __init__(self, config):
        super().__init__(config)
        self._state.properties = {
            "locked": True,
            "battery_pct": 95.0,
            "auto_lock_seconds": 300,
            "last_activity": "locked",
        }
        self._state.power = True  # Lock is always powered

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        match action:
            case "lock":
                self._state.properties["locked"] = True
                self._state.properties["last_activity"] = "locked"
                self._drain_battery(0.1)
                return {"success": True, "locked": True}

            case "unlock":
                self._state.properties["locked"] = False
                self._state.properties["last_activity"] = "unlocked"
                self._drain_battery(0.2)
                return {"success": True, "locked": False}

            case "status":
                return {
                    "success": True,
                    "locked": self._state.properties["locked"],
                    "battery_pct": self._state.properties["battery_pct"],
                }

            case _:
                return {"success": False, "error": f"Unknown action: {action}"}

    def _drain_battery(self, amount: float) -> None:
        """Simulate battery drain on lock/unlock."""
        current = self._state.properties.get("battery_pct", 100)
        self._state.properties["battery_pct"] = max(0, round(current - amount, 1))

    def _get_telemetry(self) -> dict[str, Any] | None:
        base = super()._get_telemetry() or {}
        base.update({
            "locked": self._state.properties["locked"],
            "battery_pct": self._state.properties["battery_pct"],
        })
        return base
