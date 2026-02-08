"""LangChain tools for querying home state -- used by agents."""

from langchain_core.tools import tool

from src.devices.registry import device_registry
from src.models.device import DeviceType

import json


@tool
async def get_device_state(device_id: str) -> str:
    """Get the current state of a specific device.

    Args:
        device_id: The device ID to query
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"
    return json.dumps(device.get_state_dict(), indent=2)


@tool
async def get_all_device_states() -> str:
    """Get states of all devices in the home, grouped by room."""
    states = device_registry.get_all_states()
    return json.dumps(states, indent=2)


@tool
async def get_energy_summary() -> str:
    """Get the current energy consumption and production summary."""
    summary = device_registry.get_energy_summary()
    return json.dumps(summary, indent=2)


@tool
async def get_devices_in_room(room_id: str) -> str:
    """Get all devices in a specific room.

    Args:
        room_id: The room ID (e.g., 'living_room', 'bedroom', 'kitchen', 'office')
    """
    devices = device_registry.get_devices_by_room(room_id)
    if not devices:
        return f"No devices found in room: {room_id}"
    return json.dumps([d.get_state_dict() for d in devices], indent=2)


@tool
async def get_devices_by_type(device_type: str) -> str:
    """Get all devices of a specific type.

    Args:
        device_type: One of: light, thermostat, lock, battery, coffee_maker, sensor, smart_plug
    """
    try:
        dt = DeviceType(device_type)
    except ValueError:
        return f"Error: Invalid device type '{device_type}'"
    devices = device_registry.get_devices_by_type(dt)
    return json.dumps([d.get_state_dict() for d in devices], indent=2)


QUERY_TOOLS = [
    get_device_state,
    get_all_device_states,
    get_energy_summary,
    get_devices_in_room,
    get_devices_by_type,
]
