"""SQLite event store for device events, agent decisions, system logs, and patterns."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any

import aiosqlite

from config import settings
from src.models.events import Event, EventType

logger = logging.getLogger(__name__)


class EventStore:
    """Async SQLite-based event store."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or settings.sqlite_db_path
        self._db: aiosqlite.Connection | None = None

    async def initialize(self) -> None:
        """Create database and tables."""
        self._db = await aiosqlite.connect(self._db_path)

        # Events table (existing)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                source TEXT,
                data TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(event_type)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp
            ON events(timestamp)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_source
            ON events(source)
        """)

        # Patterns table (persistent pattern storage)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                pattern_id TEXT PRIMARY KEY,
                pattern_type TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                data TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_type
            ON patterns(pattern_type)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_patterns_approved
            ON patterns(approved)
        """)

        await self._db.commit()
        logger.info(f"Event store initialized at {self._db_path}")

    async def log_event(self, event: Event) -> str:
        """Store an event and return its ID."""
        if not self._db:
            await self.initialize()

        event_id = event.event_id or str(uuid.uuid4())[:8]
        await self._db.execute(
            "INSERT INTO events (event_id, event_type, source, data, timestamp) VALUES (?, ?, ?, ?, ?)",
            (
                event_id,
                event.event_type.value,
                event.source,
                json.dumps(event.data),
                event.timestamp.isoformat(),
            ),
        )
        await self._db.commit()
        return event_id

    async def get_events(
        self,
        event_type: EventType | None = None,
        source: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Event]:
        """Query events with optional filters."""
        if not self._db:
            await self.initialize()

        query = "SELECT event_id, event_type, source, data, timestamp FROM events WHERE 1=1"
        params: list[Any] = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        if source:
            query += " AND source = ?"
            params.append(source)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        async with self._db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        return [
            Event(
                event_id=row[0],
                event_type=EventType(row[1]),
                source=row[2],
                data=json.loads(row[3]) if row[3] else {},
                timestamp=datetime.fromisoformat(row[4]),
            )
            for row in rows
        ]

    async def get_device_events(
        self, device_id: str, limit: int = 50
    ) -> list[Event]:
        """Get events for a specific device."""
        return await self.get_events(source=device_id, limit=limit)

    async def get_recent_events(self, limit: int = 50) -> list[Event]:
        """Get most recent events across all sources."""
        return await self.get_events(limit=limit)

    # ------------------------------------------------------------------
    # Pattern persistence
    # ------------------------------------------------------------------

    async def save_pattern(self, pattern_id: str, pattern_data: dict[str, Any]) -> None:
        """Insert or update a pattern in the database."""
        if not self._db:
            await self.initialize()

        now = datetime.now().isoformat()
        data_json = json.dumps(pattern_data)

        await self._db.execute(
            """INSERT INTO patterns (pattern_id, pattern_type, display_name, description,
                                    data, approved, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(pattern_id) DO UPDATE SET
                   data = excluded.data,
                   approved = excluded.approved,
                   updated_at = excluded.updated_at""",
            (
                pattern_id,
                pattern_data.get("pattern_type", "routine"),
                pattern_data.get("display_name", ""),
                pattern_data.get("description", ""),
                data_json,
                1 if pattern_data.get("approved", False) else 0,
                pattern_data.get("created_at", now),
                now,
            ),
        )
        await self._db.commit()

    async def load_all_patterns(self) -> list[dict[str, Any]]:
        """Load all patterns from the database."""
        if not self._db:
            await self.initialize()

        async with self._db.execute(
            "SELECT pattern_id, data FROM patterns ORDER BY created_at"
        ) as cursor:
            rows = await cursor.fetchall()

        patterns = []
        for row in rows:
            try:
                data = json.loads(row[1])
                data["pattern_id"] = row[0]  # ensure ID is in the dict
                patterns.append(data)
            except json.JSONDecodeError:
                logger.warning(f"Corrupted pattern data for {row[0]}")
        return patterns

    async def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern from the database."""
        if not self._db:
            await self.initialize()

        cursor = await self._db.execute(
            "DELETE FROM patterns WHERE pattern_id = ?", (pattern_id,)
        )
        await self._db.commit()
        return cursor.rowcount > 0

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            logger.info("Event store closed")


# Singleton
event_store = EventStore()
