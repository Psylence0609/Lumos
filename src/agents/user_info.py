"""User Info Agent -- GPS location tracking and Google Calendar context."""

import asyncio
import logging
import math
import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from config import settings
from src.agents.base import BaseAgent, AgentStatus
from src.integrations.google_calendar import calendar_client, CalendarEvent
from src.storage.event_store import event_store
from src.models.events import Event, EventType
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)


class UserLocation(str, Enum):
    HOME = "home"
    AWAY = "away"
    ARRIVING = "arriving"
    LEAVING = "leaving"


class UserInfoAgent(BaseAgent):
    """Tracks user location via GPS and context from Google Calendar."""

    def __init__(self):
        super().__init__("user_info", "User Info Agent")
        self._location = UserLocation.HOME
        self._previous_location = UserLocation.HOME
        self._gps_lat: float = settings.home_latitude
        self._gps_lon: float = settings.home_longitude
        self._calendar_context: dict[str, Any] = {}
        self._gps_override: UserLocation | None = None
        self._gps_coords_override: tuple[float, float] | None = None
        self._poll_task: asyncio.Task | None = None
        self._calendar_events: list[CalendarEvent] = []

    @property
    def location(self) -> UserLocation:
        return self._gps_override or self._location

    @property
    def calendar_context(self) -> dict[str, Any]:
        return self._calendar_context

    @property
    def current_context(self) -> dict[str, Any]:
        return {
            "location": self.location.value,
            "gps": {"lat": self._gps_lat, "lon": self._gps_lon},
            "calendar": self._calendar_context,
            "at_home": self.location in (UserLocation.HOME, UserLocation.ARRIVING),
        }

    async def start(self) -> None:
        await super().start()
        await calendar_client.initialize()
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        await super().stop()

    async def _poll_loop(self) -> None:
        """Poll calendar and check location periodically."""
        try:
            while True:
                await self.run()
                await asyncio.sleep(60)  # Check every minute
        except asyncio.CancelledError:
            pass

    async def run(self, *args, **kwargs) -> dict[str, Any]:
        """Update user context from GPS and Calendar."""
        self._status = AgentStatus.RUNNING

        try:
            # Update calendar context
            self._calendar_context = await calendar_client.get_current_context()
            self._calendar_events = await calendar_client.get_upcoming_events(hours_ahead=4)

            # Check for location transitions
            old_location = self._location
            if self._gps_override:
                self._location = self._gps_override
            else:
                self._location = self._calculate_location()

            # Detect transitions
            if old_location != self._location:
                self._previous_location = old_location
                await self._handle_location_transition(old_location, self._location)

            context = self.current_context
            self._record_action(
                action=f"Location: {self._location.value}, Calendar: {self._calendar_context.get('suggested_mode', 'normal')}",
                reasoning=f"GPS: ({self._gps_lat:.4f}, {self._gps_lon:.4f}), Events: {len(self._calendar_events)}",
            )

            # Broadcast to WebSocket
            await ws_manager.broadcast("user_context", context)

            self._status = AgentStatus.IDLE
            return context

        except Exception as e:
            logger.error(f"User info agent error: {e}")
            self._status = AgentStatus.ERROR
            self._error = str(e)
            return self.current_context

    def _calculate_location(self) -> UserLocation:
        """Calculate location status based on GPS distance from home."""
        if self._gps_coords_override:
            lat, lon = self._gps_coords_override
        else:
            lat, lon = self._gps_lat, self._gps_lon

        distance = self._haversine_distance(
            lat, lon, settings.home_latitude, settings.home_longitude
        )

        if distance < settings.geofence_radius_meters:
            return UserLocation.HOME
        elif distance < settings.geofence_radius_meters * 3:
            # Within 3x geofence -- arriving or leaving
            if self._previous_location == UserLocation.AWAY:
                return UserLocation.ARRIVING
            else:
                return UserLocation.LEAVING
        else:
            return UserLocation.AWAY

    async def _handle_location_transition(self, old: UserLocation, new: UserLocation) -> None:
        """Handle user location state transition."""
        logger.info(f"User location: {old.value} -> {new.value}")

        await event_store.log_event(Event(
            event_id=str(uuid.uuid4())[:8],
            event_type=EventType.USER_ACTION,
            source=self.agent_id,
            data={
                "transition": f"{old.value} -> {new.value}",
                "gps": {"lat": self._gps_lat, "lon": self._gps_lon},
            },
        ))

        await ws_manager.broadcast("location_change", {
            "previous": old.value,
            "current": new.value,
        })

    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two GPS coordinates in meters."""
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # -- Simulation overrides --

    def set_location_override(self, location: str) -> None:
        """Set GPS location override (from simulation dashboard)."""
        try:
            self._gps_override = UserLocation(location)
        except ValueError:
            logger.warning(f"Invalid location override: {location}")

    def clear_location_override(self) -> None:
        self._gps_override = None

    def set_gps_coordinates(self, lat: float, lon: float) -> None:
        """Set simulated GPS coordinates."""
        self._gps_coords_override = (lat, lon)
        self._gps_lat = lat
        self._gps_lon = lon

    def set_calendar_override(self, events: list[CalendarEvent]) -> None:
        """Set calendar override."""
        calendar_client.set_override(events)


# Singleton
user_info_agent = UserInfoAgent()
