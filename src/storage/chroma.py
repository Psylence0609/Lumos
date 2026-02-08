"""ChromaDB wrapper for pattern storage and vector-based retrieval."""

import json
import logging
from datetime import datetime
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


class ChromaStore:
    """ChromaDB wrapper for storing and querying device events and patterns."""

    def __init__(self, persist_dir: str | None = None):
        self._persist_dir = persist_dir or settings.chroma_persist_dir
        self._client = None
        self._events_collection = None
        self._patterns_collection = None

    async def initialize(self) -> None:
        """Initialize ChromaDB client and collections."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            self._client = chromadb.Client(ChromaSettings(
                persist_directory=self._persist_dir,
                anonymized_telemetry=False,
            ))

            self._events_collection = self._client.get_or_create_collection(
                name="device_events",
                metadata={"description": "Time-stamped device events for pattern mining"},
            )

            self._patterns_collection = self._client.get_or_create_collection(
                name="detected_patterns",
                metadata={"description": "Detected usage patterns"},
            )

            logger.info(f"ChromaDB initialized at {self._persist_dir}")
        except Exception as e:
            logger.error(f"ChromaDB initialization error: {e}")

    async def add_event(
        self,
        event_id: str,
        device_id: str,
        action: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a device event for pattern mining."""
        if not self._events_collection:
            return

        try:
            doc = f"{device_id} {action} {json.dumps(metadata or {})}"
            meta = {
                "device_id": device_id,
                "action": action,
                "timestamp": datetime.now().isoformat(),
                "hour": datetime.now().hour,
                "day_of_week": datetime.now().weekday(),
                **(metadata or {}),
            }
            # Filter out non-string values for ChromaDB metadata
            clean_meta = {k: str(v) for k, v in meta.items()}

            self._events_collection.add(
                documents=[doc],
                metadatas=[clean_meta],
                ids=[event_id],
            )
        except Exception as e:
            logger.error(f"ChromaDB add_event error: {e}")

    async def query_similar_events(
        self,
        query: str,
        n_results: int = 10,
        where: dict | None = None,
    ) -> list[dict]:
        """Query events similar to the given description."""
        if not self._events_collection:
            return []

        try:
            kwargs: dict[str, Any] = {
                "query_texts": [query],
                "n_results": n_results,
            }
            if where:
                kwargs["where"] = where

            results = self._events_collection.query(**kwargs)

            events = []
            for i, doc_id in enumerate(results["ids"][0]):
                events.append({
                    "id": doc_id,
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None,
                })
            return events
        except Exception as e:
            logger.error(f"ChromaDB query error: {e}")
            return []

    async def add_pattern(
        self,
        pattern_id: str,
        description: str,
        metadata: dict[str, Any],
    ) -> None:
        """Store a detected pattern."""
        if not self._patterns_collection:
            return

        try:
            clean_meta = {k: str(v) for k, v in metadata.items()}
            self._patterns_collection.add(
                documents=[description],
                metadatas=[clean_meta],
                ids=[pattern_id],
            )
        except Exception as e:
            logger.error(f"ChromaDB add_pattern error: {e}")

    async def get_all_events(self, limit: int = 1000) -> list[dict]:
        """Get all stored events (for pattern analysis)."""
        if not self._events_collection:
            return []

        try:
            count = self._events_collection.count()
            if count == 0:
                return []

            results = self._events_collection.get(
                limit=min(limit, count),
                include=["documents", "metadatas"],
            )

            events = []
            for i, doc_id in enumerate(results["ids"]):
                events.append({
                    "id": doc_id,
                    "document": results["documents"][i],
                    "metadata": results["metadatas"][i],
                })
            return events
        except Exception as e:
            logger.error(f"ChromaDB get_all_events error: {e}")
            return []


# Singleton
chroma_store = ChromaStore()
