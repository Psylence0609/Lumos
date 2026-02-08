"""Device registry: loads devices from YAML config and manages lifecycle."""

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
from src.models.device import DeviceConfig, DeviceType, EnergyProfile, PriorityTier

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


# Singleton
device_registry = DeviceRegistry()
