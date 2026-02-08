"""WebSocket connection manager for real-time frontend updates."""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages to all clients."""

    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self._connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self._connections)}")

    async def broadcast(self, message_type: str, data: Any) -> None:
        """Broadcast a typed message to all connected clients."""
        payload = json.dumps({"type": message_type, "data": data})
        dead: list[WebSocket] = []

        async with self._lock:
            connections = list(self._connections)

        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    if ws in self._connections:
                        self._connections.remove(ws)

    async def send_to(self, websocket: WebSocket, message_type: str, data: Any) -> None:
        """Send a typed message to a specific client."""
        payload = json.dumps({"type": message_type, "data": data})
        try:
            await websocket.send_text(payload)
        except Exception:
            await self.disconnect(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Singleton
ws_manager = ConnectionManager()
