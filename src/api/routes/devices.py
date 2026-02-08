"""Device REST API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.devices.registry import device_registry
from src.api.websocket import ws_manager

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceCommandRequest(BaseModel):
    action: str
    parameters: dict[str, Any] = {}


@router.get("")
async def list_devices() -> dict[str, Any]:
    """List all devices grouped by room."""
    return device_registry.get_all_states()


@router.get("/flat")
async def list_devices_flat() -> list[dict[str, Any]]:
    """List all devices as a flat list."""
    return [d.get_state_dict() for d in device_registry.devices.values()]


@router.get("/energy")
async def get_energy_summary() -> dict[str, Any]:
    """Get energy consumption and production summary."""
    return device_registry.get_energy_summary()


@router.get("/{device_id}")
async def get_device(device_id: str) -> dict[str, Any]:
    """Get a specific device's state."""
    device = device_registry.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")
    return device.get_state_dict()


@router.post("/{device_id}/command")
async def send_device_command(device_id: str, cmd: DeviceCommandRequest) -> dict[str, Any]:
    """Send a command to a specific device."""
    device = device_registry.get_device(device_id)
    if not device:
        raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

    result = await device.execute_action(cmd.action, cmd.parameters)

    # Broadcast state update to WebSocket clients
    await ws_manager.broadcast("device_state", device.get_state_dict())

    return result
