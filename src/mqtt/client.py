"""Async MQTT client manager for the smart home system."""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import aiomqtt

from config import settings

logger = logging.getLogger(__name__)

# Type alias for message handlers
MessageHandler = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class MQTTClient:
    """Async MQTT client wrapper with pub/sub capabilities."""

    def __init__(self):
        self._client: aiomqtt.Client | None = None
        self._subscriptions: dict[str, list[MessageHandler]] = {}
        self._connected = False
        self._listen_task: asyncio.Task | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Connect to the MQTT broker and start listening."""
        try:
            self._client = aiomqtt.Client(
                hostname=settings.mqtt_host,
                port=settings.mqtt_port,
            )
            await self._client.__aenter__()
            self._connected = True
            logger.info(
                f"Connected to MQTT broker at {settings.mqtt_host}:{settings.mqtt_port}"
            )

            # Re-subscribe to all existing subscriptions
            for topic in self._subscriptions:
                await self._client.subscribe(topic)

            # Start the listener loop
            self._listen_task = asyncio.create_task(self._listen())

        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from the MQTT broker."""
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self._client and self._connected:
            await self._client.__aexit__(None, None, None)
            self._connected = False
            logger.info("Disconnected from MQTT broker")

    async def publish(self, topic: str, payload: dict[str, Any]) -> None:
        """Publish a JSON message to a topic."""
        if not self._client or not self._connected:
            logger.warning(f"Not connected, cannot publish to {topic}")
            return

        message = json.dumps(payload)
        await self._client.publish(topic, message.encode())
        logger.debug(f"Published to {topic}: {message[:200]}")

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to a topic with a message handler."""
        if topic not in self._subscriptions:
            self._subscriptions[topic] = []
            if self._client and self._connected:
                await self._client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")

        self._subscriptions[topic].append(handler)

    async def unsubscribe(self, topic: str) -> None:
        """Unsubscribe from a topic."""
        if topic in self._subscriptions:
            del self._subscriptions[topic]
            if self._client and self._connected:
                await self._client.unsubscribe(topic)
                logger.info(f"Unsubscribed from {topic}")

    async def _listen(self) -> None:
        """Listen for incoming messages and dispatch to handlers."""
        if not self._client:
            return

        try:
            async for message in self._client.messages:
                topic = str(message.topic)
                try:
                    payload = json.loads(message.payload.decode())
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning(f"Invalid message on {topic}")
                    continue

                # Find matching handlers (supports wildcards)
                for sub_topic, handlers in self._subscriptions.items():
                    if self._topic_matches(sub_topic, topic):
                        for handler in handlers:
                            try:
                                await handler(topic, payload)
                            except Exception as e:
                                logger.error(
                                    f"Handler error for {topic}: {e}", exc_info=True
                                )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"MQTT listener error: {e}", exc_info=True)

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern (supports + and # wildcards)."""
        pattern_parts = pattern.split("/")
        topic_parts = topic.split("/")

        for i, part in enumerate(pattern_parts):
            if part == "#":
                return True
            if i >= len(topic_parts):
                return False
            if part != "+" and part != topic_parts[i]:
                return False

        return len(pattern_parts) == len(topic_parts)


# Singleton instance
mqtt_client = MQTTClient()
