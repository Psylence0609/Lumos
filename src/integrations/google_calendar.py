"""Google Calendar API client for user context."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)


class CalendarEvent(BaseModel):
    """Parsed calendar event."""
    event_id: str = ""
    summary: str = ""
    start: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    location: str = ""
    description: str = ""
    is_all_day: bool = False


class GoogleCalendarClient:
    """Client for Google Calendar API.

    Supports real Google Calendar integration via OAuth, or simulation override.
    """

    def __init__(self):
        self._credentials = None
        self._service = None
        self._override_events: list[CalendarEvent] | None = None
        self._initialized = False

    def set_override(self, events: list[CalendarEvent]) -> None:
        """Set simulation override for calendar events."""
        self._override_events = events

    def clear_override(self) -> None:
        """Clear simulation override."""
        self._override_events = None

    async def initialize(self) -> bool:
        """Initialize Google Calendar API with OAuth credentials."""
        if self._initialized:
            return True

        client_id = settings.google_client_id
        client_secret = settings.google_client_secret

        if not client_id or client_id == "your_google_client_id_here":
            logger.info("Google Calendar not configured, using simulation mode")
            return False

        try:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # This requires a token.json from the OAuth flow
            # The setup_google_oauth.py script handles the initial auth
            import os
            token_path = os.path.join(os.path.dirname(__file__), "../../token.json")

            if os.path.exists(token_path):
                self._credentials = Credentials.from_authorized_user_file(
                    token_path,
                    scopes=["https://www.googleapis.com/auth/calendar.readonly"],
                )
                self._service = build("calendar", "v3", credentials=self._credentials)
                self._initialized = True
                logger.info("Google Calendar API initialized")
                return True
            else:
                logger.warning("Google Calendar token not found. Run setup_google_oauth.py first.")
                return False

        except Exception as e:
            logger.error(f"Failed to initialize Google Calendar: {e}")
            return False

    async def get_upcoming_events(self, hours_ahead: int = 2) -> list[CalendarEvent]:
        """Get upcoming events within the specified time window."""
        if self._override_events is not None:
            return self._override_events

        if not self._initialized or not self._service:
            return []

        try:
            now = datetime.now(timezone.utc)
            time_min = now.isoformat()
            time_max = (now + timedelta(hours=hours_ahead)).isoformat()

            events_result = self._service.events().list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=10,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = []
            for item in events_result.get("items", []):
                start = item.get("start", {})
                end = item.get("end", {})

                is_all_day = "date" in start
                start_dt = (
                    datetime.fromisoformat(start.get("date", ""))
                    if is_all_day
                    else datetime.fromisoformat(start.get("dateTime", "").replace("Z", "+00:00"))
                )
                end_dt = (
                    datetime.fromisoformat(end.get("date", ""))
                    if is_all_day
                    else datetime.fromisoformat(end.get("dateTime", "").replace("Z", "+00:00"))
                )

                events.append(CalendarEvent(
                    event_id=item.get("id", ""),
                    summary=item.get("summary", ""),
                    start=start_dt,
                    end=end_dt,
                    location=item.get("location", ""),
                    description=item.get("description", ""),
                    is_all_day=is_all_day,
                ))

            return events

        except Exception as e:
            logger.error(f"Google Calendar API error: {e}")
            return []

    # Keywords that map to specific home modes
    MEETING_KEYWORDS = ("meeting", "call", "interview", "standup", "sync", "1:1", "review", "demo", "presentation", "webinar", "zoom", "teams")
    SLEEP_KEYWORDS = ("sleep", "bed", "night", "nap", "rest")
    ACTIVE_KEYWORDS = ("workout", "exercise", "gym", "run", "yoga", "training")
    FOCUS_KEYWORDS = ("focus", "deep work", "study", "coding", "writing", "exam")

    PREPARATION_WINDOW_MINUTES = 15  # How far ahead to start preparing

    def _infer_mode_from_summary(self, summary: str) -> str:
        """Infer the suggested home mode from an event summary."""
        summary_lower = summary.lower()
        if any(w in summary_lower for w in self.SLEEP_KEYWORDS):
            return "sleep"
        if any(w in summary_lower for w in self.MEETING_KEYWORDS):
            return "do_not_disturb"
        if any(w in summary_lower for w in self.FOCUS_KEYWORDS):
            return "focus"
        if any(w in summary_lower for w in self.ACTIVE_KEYWORDS):
            return "active"
        return "normal"

    async def get_current_context(self) -> dict[str, Any]:
        """Get user context from calendar events.

        Returns a dict with:
        - has_events: bool
        - in_meeting: bool
        - current_event: str (if in meeting)
        - next_event: dict | None (summary, starts_in_minutes, location)
        - suggested_mode: one of normal, do_not_disturb, focus, sleep, active, preparing_for_meeting
        - preparing_for: str (event summary, only when suggested_mode == preparing_for_meeting)
        - meeting_ends_in_minutes: int (only when in_meeting)
        """
        events = await self.get_upcoming_events(hours_ahead=4)

        context: dict[str, Any] = {
            "has_events": len(events) > 0,
            "in_meeting": False,
            "next_event": None,
            "suggested_mode": "normal",
        }

        now = datetime.now(timezone.utc)
        for event in events:
            # Ensure both sides are tz-aware
            ev_start = event.start if event.start.tzinfo else event.start.replace(tzinfo=timezone.utc)
            ev_end = event.end if event.end.tzinfo else event.end.replace(tzinfo=timezone.utc)

            if ev_start <= now <= ev_end:
                # Currently in this event
                context["in_meeting"] = True
                context["current_event"] = event.summary
                context["meeting_ends_in_minutes"] = max(0, int((ev_end - now).total_seconds() / 60))

                mode = self._infer_mode_from_summary(event.summary)
                context["suggested_mode"] = mode if mode != "normal" else "do_not_disturb"
                break

            elif ev_start > now:
                # Future event
                minutes_until = int((ev_start - now).total_seconds() / 60)
                context["next_event"] = {
                    "summary": event.summary,
                    "starts_in_minutes": minutes_until,
                    "location": event.location,
                }

                # If a meeting/focus event is coming within the prep window,
                # switch to preparing_for_meeting so the house can get ready
                inferred = self._infer_mode_from_summary(event.summary)
                if inferred in ("do_not_disturb", "focus") and minutes_until <= self.PREPARATION_WINDOW_MINUTES:
                    context["suggested_mode"] = "preparing_for_meeting"
                    context["preparing_for"] = event.summary
                    context["event_starts_in_minutes"] = minutes_until
                break

        return context


# Singleton
calendar_client = GoogleCalendarClient()
