"""LangChain tools for energy management -- used by Orchestrator."""

import json

from langchain_core.tools import tool

from src.devices.registry import device_registry
from src.models.device import DeviceType, PriorityTier


@tool
async def get_energy_budget() -> str:
    """Get the current energy budget: available power vs consumption."""
    summary = device_registry.get_energy_summary()
    battery_device = device_registry.get_devices_by_type(DeviceType.BATTERY)
    battery_pct = 0
    if battery_device:
        battery_pct = battery_device[0].state.properties.get("battery_pct", 0)

    budget = {
        "total_consumption_watts": summary["total_consumption_watts"],
        "solar_generation_watts": summary["solar_generation_watts"],
        "battery_pct": battery_pct,
        "net_from_grid_watts": summary["net_grid_watts"],
        "energy_status": (
            "surplus" if summary["net_grid_watts"] < 0
            else "balanced" if summary["net_grid_watts"] < 500
            else "deficit"
        ),
    }
    return json.dumps(budget, indent=2)


@tool
async def get_deprioritization_plan() -> str:
    """Generate a prioritized list of devices that can be turned off to save energy.
    Returns devices sorted by priority (lowest priority first)."""
    devices_by_priority: list[dict] = []

    for device in device_registry.devices.values():
        if not device.state.power:
            continue
        if device.state.priority_tier == PriorityTier.CRITICAL:
            continue  # Never deprioritize critical devices

        devices_by_priority.append({
            "device_id": device.device_id,
            "display_name": device.display_name,
            "room": device.room,
            "priority_tier": device.state.priority_tier.value,
            "current_watts": device.state.current_watts,
            "negotiation_flexibility": device.state.negotiation_flexibility,
        })

    # Sort: lowest priority + highest flexibility first
    tier_order = {"optional": 0, "low": 1, "medium": 2, "high": 3}
    devices_by_priority.sort(
        key=lambda d: (tier_order.get(d["priority_tier"], 2), -d["negotiation_flexibility"])
    )

    return json.dumps({
        "deprioritization_order": devices_by_priority,
        "total_saveable_watts": sum(d["current_watts"] for d in devices_by_priority),
    }, indent=2)


@tool
async def execute_energy_saving(level: str) -> str:
    """Execute energy saving by turning off non-essential devices.

    Args:
        level: Saving level - 'mild' (optional+low), 'moderate' (+ medium), 'aggressive' (+ high)
    """
    tier_cutoffs = {
        "mild": {"optional", "low"},
        "moderate": {"optional", "low", "medium"},
        "aggressive": {"optional", "low", "medium", "high"},
    }

    cutoff = tier_cutoffs.get(level, tier_cutoffs["mild"])
    turned_off = []

    for device in device_registry.devices.values():
        if not device.state.power:
            continue
        if device.state.priority_tier.value in cutoff:
            result = await device.execute_action("off")
            if result.get("success"):
                turned_off.append({
                    "device_id": device.device_id,
                    "display_name": device.display_name,
                    "saved_watts": device.state.energy_profile.active_watts,
                })

    return json.dumps({
        "level": level,
        "devices_turned_off": turned_off,
        "total_watts_saved": sum(d["saved_watts"] for d in turned_off),
    }, indent=2)


ENERGY_TOOLS = [
    get_energy_budget,
    get_deprioritization_plan,
    execute_energy_saving,
]
