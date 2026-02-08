"""LangChain tools for device control -- used by Home State Agent."""

import logging
from typing import Any

from langchain_core.tools import tool

from src.devices.registry import device_registry
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)


@tool
async def set_thermostat(device_id: str, temperature: float, mode: str = "auto") -> str:
    """Set a thermostat's target temperature and mode.

    Args:
        device_id: The thermostat device ID (e.g., 'thermostat_living')
        temperature: Target temperature in Fahrenheit (60-85)
        mode: Operating mode - one of: heat, cool, auto, eco, off
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"

    result = await device.execute_action("set_temperature", {"temperature": temperature})
    if result.get("success") and mode:
        await device.execute_action("set_mode", {"mode": mode})

    await ws_manager.broadcast("device_state", device.get_state_dict())
    return f"Thermostat {device_id} set to {temperature}F in {mode} mode" if result.get("success") else f"Error: {result.get('error')}"


@tool
async def set_light(device_id: str, brightness: int = 100, r: int = 255, g: int = 255, b: int = 255) -> str:
    """Control a smart light's brightness and color.

    Args:
        device_id: The light device ID (e.g., 'light_living_main')
        brightness: Brightness level 0-100 (0 turns off)
        r: Red color value 0-255
        g: Green color value 0-255
        b: Blue color value 0-255
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"

    if brightness == 0:
        result = await device.execute_action("off")
    else:
        result = await device.execute_action("on", {"brightness": brightness})
        if r != 255 or g != 255 or b != 255:
            await device.execute_action("color", {"r": r, "g": g, "b": b})

    await ws_manager.broadcast("device_state", device.get_state_dict())
    return f"Light {device_id} set to brightness {brightness}" if result.get("success") else f"Error: {result.get('error')}"


@tool
async def control_lock(device_id: str, action: str) -> str:
    """Lock or unlock a smart lock.

    Args:
        device_id: The lock device ID (e.g., 'lock_front_door')
        action: Either 'lock' or 'unlock'
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"

    if action not in ("lock", "unlock"):
        return f"Error: Invalid action '{action}'. Must be 'lock' or 'unlock'"

    result = await device.execute_action(action)
    await ws_manager.broadcast("device_state", device.get_state_dict())
    return f"Lock {device_id} {action}ed" if result.get("success") else f"Error: {result.get('error')}"


@tool
async def control_smart_plug(device_id: str, action: str) -> str:
    """Turn a smart plug on or off.

    Args:
        device_id: The smart plug device ID (e.g., 'plug_living_tv')
        action: Either 'on' or 'off'
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"

    result = await device.execute_action(action)
    await ws_manager.broadcast("device_state", device.get_state_dict())
    return f"Smart plug {device_id} turned {action}" if result.get("success") else f"Error: {result.get('error')}"


@tool
async def control_coffee_maker(device_id: str, action: str, strength: str = "medium") -> str:
    """Control the coffee maker.

    Args:
        device_id: The coffee maker device ID (e.g., 'coffee_maker')
        action: One of: brew, off, keep_warm
        strength: Brew strength - light, medium, or strong
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"

    params = {"strength": strength} if action == "brew" else {}
    result = await device.execute_action(action, params)
    await ws_manager.broadcast("device_state", device.get_state_dict())
    return f"Coffee maker {action}" if result.get("success") else f"Error: {result.get('error')}"


@tool
async def set_battery_mode(device_id: str, mode: str) -> str:
    """Set the home battery operating mode.

    Args:
        device_id: The battery device ID (e.g., 'battery_main')
        mode: One of: charge, discharge, auto, backup
    """
    device = device_registry.get_device(device_id)
    if not device:
        return f"Error: Device {device_id} not found"

    result = await device.execute_action("set_mode", {"mode": mode})
    await ws_manager.broadcast("device_state", device.get_state_dict())
    return f"Battery mode set to {mode}" if result.get("success") else f"Error: {result.get('error')}"


# Collect all tools for the Home State Agent
DEVICE_TOOLS = [
    set_thermostat,
    set_light,
    control_lock,
    control_smart_plug,
    control_coffee_maker,
    set_battery_mode,
]
