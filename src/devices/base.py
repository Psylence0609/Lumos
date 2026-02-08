"""Base device class with MQTT pub/sub capabilities."""

import asyncio
import json
import logging
import random
from datetime import datetime
from typing import Any

from src.models.device import DeviceConfig, DeviceState, DeviceType, EnergyProfile, PriorityTier
from src.mqtt.client import mqtt_client
from src.mqtt.topics import Topics

logger = logging.getLogger(__name__)


class BaseDevice:
    """Base class for all simulated IoT devices.

    Provides MQTT communication, state management, and simulated behavior.
    """

    def __init__(self, config: DeviceConfig):
        self.config = config
        self.device_id = config.id
        self.device_type = config.type
        self.display_name = config.display_name
        self.room = config.room
        self.capabilities = config.capabilities

        # State
        self._state = DeviceState(
            device_id=config.id,
            device_type=config.type,
            display_name=config.display_name,
            room=config.room,
            energy_profile=config.energy_profile,
            priority_tier=config.priority_tier,
            negotiation_flexibility=config.negotiation_flexibility,
        )

        # Simulation
        self._failure_probability = 0.0  # Set via simulation override
        self._forced_offline = False
        self._update_task: asyncio.Task | None = None

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def is_online(self) -> bool:
        return self._state.online and not self._forced_offline

    async def start(self) -> None:
        """Start the device: subscribe to command topic and begin telemetry."""
        command_topic = Topics.device_command(self.device_id)
        await mqtt_client.subscribe(command_topic, self._handle_command)
        await self._publish_state()
        self._update_task = asyncio.create_task(self._telemetry_loop())
        logger.info(f"Device {self.device_id} started")

    async def stop(self) -> None:
        """Stop the device."""
        if self._update_task:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
        command_topic = Topics.device_command(self.device_id)
        await mqtt_client.unsubscribe(command_topic)
        logger.info(f"Device {self.device_id} stopped")

    async def execute_action(self, action: str, parameters: dict[str, Any] = {}) -> dict[str, Any]:
        """Execute an action on this device. Override in subclasses."""
        if not self.is_online:
            return {"success": False, "error": "Device is offline"}

        # Simulate random failure
        if random.random() < self._failure_probability:
            self._state.online = False
            await self._publish_state()
            return {"success": False, "error": "Device malfunction"}

        # Simulate realistic delay
        await asyncio.sleep(random.uniform(0.1, 0.3))

        result = await self._process_action(action, parameters)
        self._state.last_updated = datetime.now()
        self._update_energy_usage()
        await self._publish_state()
        return result

    async def _process_action(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        """Process a specific action. Override in subclasses."""
        return {"success": False, "error": f"Unknown action: {action}"}

    def _update_energy_usage(self) -> None:
        """Update current wattage based on state."""
        if self._state.power:
            self._state.current_watts = self._state.energy_profile.active_watts
        else:
            self._state.current_watts = self._state.energy_profile.idle_watts

    async def _publish_state(self) -> None:
        """Publish current state to MQTT."""
        topic = Topics.device_state(self.device_id)
        await mqtt_client.publish(topic, self._state.to_mqtt_payload())

    async def _handle_command(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle incoming MQTT command."""
        action = payload.get("action", "")
        parameters = payload.get("parameters", {})
        logger.info(f"Device {self.device_id} received command: {action}")
        result = await self.execute_action(action, parameters)
        logger.info(f"Device {self.device_id} action result: {result}")

    async def _telemetry_loop(self) -> None:
        """Periodically publish telemetry data."""
        try:
            # Stagger initial delay so devices don't all publish at the same instant
            await asyncio.sleep(random.uniform(1, 10))
            while True:
                await asyncio.sleep(30)
                if self.is_online:
                    telemetry = self._get_telemetry()
                    if telemetry:
                        topic = Topics.device_telemetry(self.device_id)
                        await mqtt_client.publish(topic, telemetry)
        except asyncio.CancelledError:
            pass

    def _get_telemetry(self) -> dict[str, Any] | None:
        """Get telemetry data. Override in subclasses for sensor-specific data."""
        return {
            "device_id": self.device_id,
            "current_watts": self._state.current_watts,
            "online": self._state.online,
            "timestamp": datetime.now().isoformat(),
        }

    def set_forced_offline(self, offline: bool) -> None:
        """Force device online/offline (simulation control)."""
        self._forced_offline = offline
        self._state.online = not offline

    def set_failure_probability(self, probability: float) -> None:
        """Set random failure probability (simulation control)."""
        self._failure_probability = max(0.0, min(1.0, probability))

    def get_state_dict(self) -> dict[str, Any]:
        """Get full state as a dictionary."""
        return self._state.to_mqtt_payload()
