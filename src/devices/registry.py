"""Device registry: loads devices from YAML config and manages lifecycle.

Also provides helper methods that dynamically derive information from the
registered devices — critical-device sets, action references for LLM prompts,
non-essential device lists, etc.  This avoids hardcoding device IDs or
capability text across multiple agents.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from src.devices.base import BaseDevice
from src.devices.battery import BatteryDevice
from src.devices.coffee_maker import CoffeeMakerDevice
from src.devices.light import LightDevice
from src.devices.lock import LockDevice
from src.devices.sensor import SensorDevice
from src.devices.smart_plug import SmartPlugDevice
from src.devices.thermostat import ThermostatDevice
from src.devices.water_heater import WaterHeaterDevice
from src.models.device import (
    DeviceConfig,
    DeviceType,
    EnergyProfile,
    PriorityTier,
    build_action_reference_text,
)

logger = logging.getLogger(__name__)

# Map device type to class
DEVICE_CLASS_MAP: dict[DeviceType, type[BaseDevice]] = {
    DeviceType.LIGHT: LightDevice,
    DeviceType.THERMOSTAT: ThermostatDevice,
    DeviceType.LOCK: LockDevice,
    DeviceType.BATTERY: BatteryDevice,
    DeviceType.COFFEE_MAKER: CoffeeMakerDevice,
    DeviceType.SENSOR: SensorDevice,
    DeviceType.SMART_PLUG: SmartPlugDevice,
    DeviceType.WATER_HEATER: WaterHeaterDevice,
}


class DeviceRegistry:
    """Manages all simulated devices in the smart home."""

    def __init__(self):
        self._devices: dict[str, BaseDevice] = {}
        self._rooms: dict[str, list[str]] = {}  # room_id -> [device_id, ...]

    @property
    def devices(self) -> dict[str, BaseDevice]:
        return self._devices

    @property
    def rooms(self) -> dict[str, list[str]]:
        return self._rooms

    def load_from_yaml(self, config_path: str) -> None:
        """Load device definitions from YAML config file."""
        path = Path(config_path)
        if not path.exists():
            logger.error(f"Device config not found: {config_path}")
            return

        with open(path) as f:
            config = yaml.safe_load(f)

        rooms = config.get("rooms", {})
        for room_id, room_data in rooms.items():
            room_name = room_data.get("display_name", room_id)
            self._rooms[room_id] = []

            for device_data in room_data.get("devices", []):
                energy = device_data.get("energy_profile", {})
                device_config = DeviceConfig(
                    id=device_data["id"],
                    type=DeviceType(device_data["type"]),
                    display_name=device_data.get("display_name", device_data["id"]),
                    capabilities=device_data.get("capabilities", []),
                    energy_profile=EnergyProfile(
                        idle_watts=energy.get("idle_watts", 0),
                        active_watts=energy.get("active_watts", 0),
                    ),
                    priority_tier=PriorityTier(
                        device_data.get("priority_tier", "medium")
                    ),
                    negotiation_flexibility=device_data.get(
                        "negotiation_flexibility", 0.5
                    ),
                    room=room_id,
                    sensor_type=device_data.get("sensor_type"),
                    battery_capacity_kwh=device_data.get("battery_capacity_kwh"),
                    solar_panel_watts=device_data.get("solar_panel_watts"),
                )

                device_cls = DEVICE_CLASS_MAP.get(device_config.type)
                if not device_cls:
                    logger.warning(f"Unknown device type: {device_config.type}")
                    continue

                device = device_cls(device_config)
                self._devices[device.device_id] = device
                self._rooms[room_id].append(device.device_id)
                logger.info(
                    f"Registered device: {device.device_id} ({device.device_type.value}) "
                    f"in {room_name}"
                )

    async def start_all(self) -> None:
        """Start all registered devices."""
        for device in self._devices.values():
            await device.start()
        logger.info(f"Started {len(self._devices)} devices")

    async def stop_all(self) -> None:
        """Stop all registered devices."""
        for device in self._devices.values():
            await device.stop()
        logger.info("All devices stopped")

    def get_device(self, device_id: str) -> BaseDevice | None:
        return self._devices.get(device_id)

    def get_devices_by_room(self, room_id: str) -> list[BaseDevice]:
        device_ids = self._rooms.get(room_id, [])
        return [self._devices[did] for did in device_ids if did in self._devices]

    def get_devices_by_type(self, device_type: DeviceType) -> list[BaseDevice]:
        return [d for d in self._devices.values() if d.device_type == device_type]

    def get_all_states(self) -> dict[str, Any]:
        """Get states of all devices, grouped by room."""
        result = {}
        for room_id, device_ids in self._rooms.items():
            result[room_id] = {
                "devices": [
                    self._devices[did].get_state_dict()
                    for did in device_ids
                    if did in self._devices
                ]
            }
        return result

    def get_energy_summary(self) -> dict[str, Any]:
        """Get total energy consumption and production summary."""
        total_consumption = 0.0
        solar_generation = 0.0
        battery_pct = 0.0
        battery_mode = "unknown"

        for device in self._devices.values():
            total_consumption += device.state.current_watts

            if device.device_type == DeviceType.BATTERY:
                solar_generation = device.state.properties.get(
                    "solar_generation_watts", 0
                )
                battery_pct = device.state.properties.get("battery_pct", 0)
                battery_mode = device.state.properties.get("mode", "unknown")

        return {
            "total_consumption_watts": round(total_consumption, 1),
            "solar_generation_watts": round(solar_generation, 1),
            "battery_pct": round(battery_pct, 1),
            "battery_mode": battery_mode,
            "net_grid_watts": round(total_consumption - solar_generation, 1),
        }

    # ------------------------------------------------------------------
    # Dynamic helpers for agents and prompts
    # ------------------------------------------------------------------

    def get_critical_device_ids(self) -> set[str]:
        """Return device IDs with CRITICAL priority — must never be turned off.

        Derived from ``priority_tier: critical`` in devices.yaml so adding a
        new critical device only requires a config change.
        """
        return {
            d.device_id
            for d in self._devices.values()
            if d.state.priority_tier == PriorityTier.CRITICAL
        }

    def get_non_essential_devices(
        self,
        *,
        exclude_types: set[DeviceType] | None = None,
        include_medium: bool = False,
    ) -> list[BaseDevice]:
        """Return powered-on devices with LOW/OPTIONAL priority.

        Args:
            exclude_types: Device types to always skip (defaults to sensor,
                           battery, lock).
            include_medium: Also include MEDIUM-priority devices.
        """
        skip_types = exclude_types or {
            DeviceType.SENSOR,
            DeviceType.BATTERY,
            DeviceType.LOCK,
        }
        tiers = {PriorityTier.LOW, PriorityTier.OPTIONAL}
        if include_medium:
            tiers.add(PriorityTier.MEDIUM)

        return [
            d
            for d in self._devices.values()
            if d.state.priority_tier in tiers
            and d.device_type not in skip_types
            and d.state.power
        ]

    def get_first_device_of_type(
        self, device_type: DeviceType, room: str | None = None
    ) -> BaseDevice | None:
        """Return the first device matching *device_type* (optionally in *room*)."""
        for d in self._devices.values():
            if d.device_type == device_type:
                if room is None or d.state.room == room:
                    return d
        return None

    def build_action_reference(self) -> str:
        """Build the device action reference block for LLM prompts.

        Delegates to the centralized schema in ``src.models.device``.
        """
        return build_action_reference_text()

    def build_critical_devices_text(self) -> str:
        """Build a human-readable list of critical devices for LLM prompts."""
        critical = self.get_critical_device_ids()
        if not critical:
            return "No critical devices configured."
        parts = []
        for did in sorted(critical):
            device = self._devices.get(did)
            name = device.display_name if device else did
            parts.append(f"{did} ({name})")
        return ", ".join(parts)


# Singleton
device_registry = DeviceRegistry()
