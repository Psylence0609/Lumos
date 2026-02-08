"""Pattern Detector Agent -- learns user routines, preferences, and energy patterns.

Patterns are persisted to SQLite so they survive app restarts.
User-defined patterns are created from natural language assertions (e.g.
"When I have a meeting, turn on my office light and computer").
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from config import settings
from src.agents.base import BaseAgent, AgentStatus
from src.integrations.openrouter import llm_client
from src.storage.chroma import chroma_store
from src.storage.event_store import event_store
from src.models.events import Event, EventType
from src.models.pattern import DetectedPattern, PatternAction, PatternType
from src.mqtt.client import mqtt_client
from src.mqtt.topics import Topics
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LLM prompts
# ---------------------------------------------------------------------------

PATTERN_ANALYSIS_PROMPT = """Analyze these smart home device events to detect recurring patterns.

EVENTS (sorted by time):
{events}

Look for:
1. ROUTINE patterns: repeated sequences at similar times (e.g., "7 AM: lights on -> coffee on -> thermostat up")
2. PREFERENCE patterns: user adjustments after automated actions (e.g., always changes thermostat from 72 to 74)
3. ENERGY patterns: correlations between usage and time/conditions

Respond with ONLY valid JSON:
{{
    "patterns": [
        {{
            "type": "routine|preference|energy",
            "name": "Short descriptive name",
            "description": "What was detected",
            "confidence": 0.0-1.0,
            "frequency": number_of_occurrences,
            "trigger": {{"time_range": "HH:MM-HH:MM", "days": ["mon","tue",...]}},
            "actions": [
                {{"device_id": "...", "action": "...", "parameters": {{}}, "delay_seconds": 0}}
            ]
        }}
    ]
}}

Only include patterns with 2+ occurrences. Be specific about device IDs."""

# Prompt for parsing a user's natural language preference into a structured pattern
PREFERENCE_PARSING_PROMPT = """You are parsing a user's smart home preference into a structured automation rule.

AVAILABLE DEVICES (with priority tiers):
{device_inventory}

USER SAID: "{user_message}"

Parse this into a structured pattern. Determine:
1. The TRIGGER — what condition causes this automation? (e.g. calendar event type, time of day, location change, specific scenario)
2. The ACTIONS — what devices should be controlled? Use EXACT device_id values from the inventory above.
3. A short DISPLAY NAME for this pattern
4. A clear DESCRIPTION of what it does

TRIGGER TYPES (pick the best one and fill in relevant fields):
- "calendar_mode": triggers when home mode changes (values: "preparing_for_meeting", "do_not_disturb", "focus", "sleep", "active", "normal")
- "location": triggers on location change (values: "home", "away", "arriving", "leaving")
- "time": triggers at a time of day (value: "HH:MM")
- "threat": triggers on a specific threat type (values: "heat_wave", "grid_strain", "power_outage", "storm", "cold_snap")
- "global": a PERMANENT constraint that applies AT ALL TIMES, regardless of trigger.
  Use this for rules like "never turn off the fridge", "don't unlock the door unless I say so", "always keep bedroom light off".
  value should be "always".
  IMPORTANT: For "global" constraints, the "actions" list should contain the PROHIBITED actions
  (i.e., what should NEVER happen). For example, "never unlock the door" → action is "unlock" on the lock device.
  The description MUST start with "NEVER" or "DON'T" to indicate this is a prohibition.

CRITICAL SAFETY RULES:
- NEVER include actions to turn off CRITICAL-priority devices (fridge plug, battery, sensors, locks — unless user explicitly asks to lock/unlock)
- When the user says "turn off unnecessary appliances" or similar, only target LOW-priority and MEDIUM-priority devices
- The fridge (plug_kitchen_fridge) is ALWAYS critical — NEVER turn it off
- Sensors are read-only — NEVER include them in actions

DEVICE ACTION REFERENCE:
- light: "on" (params: {{"brightness": 0-100}}), "off", "dim" (params: {{"brightness": 0-100}})
- thermostat: "set_temperature" (params: {{"temperature": 60-85}}), "set_mode" (params: {{"mode": "heat|cool|auto|eco|off"}})
- smart_plug: "on", "off"
- lock: "lock", "unlock"
- coffee_maker: "on" (standby), "brew" (params: {{"strength": "light|medium|strong"}}), "off"
- battery: "set_mode" (params: {{"mode": "charge|discharge|auto|backup"}})

Respond with ONLY valid JSON:
{{
    "display_name": "Short pattern name",
    "description": "Clear description of what this automation does",
    "trigger_type": "calendar_mode|location|time|threat|global",
    "trigger_value": "the specific value for the trigger type",
    "actions": [
        {{"device_id": "exact_device_id", "action": "action_name", "parameters": {{}}, "delay_seconds": 0}}
    ]
}}"""

# Prompt for UPDATING an existing pattern when user refines it
PREFERENCE_UPDATE_PROMPT = """You are updating an existing smart home automation pattern based on a new instruction from the user.

EXISTING PATTERN:
  Name: {existing_name}
  Description: {existing_description}
  Trigger: {existing_trigger_type} = {existing_trigger_value}
  Current actions:
{existing_actions}

AVAILABLE DEVICES (with priority tiers):
{device_inventory}

USER NOW SAYS: "{user_message}"

Your task: Merge the user's new instruction with the existing pattern.
- If the user says "also do X", ADD the new actions to the existing actions.
- If the user says "don't do X" or "stop doing X", REMOVE those actions.
- If the user says "change X to Y", REPLACE those specific actions.
- Keep ALL existing actions that weren't explicitly changed or removed.
- Update the display_name and description to reflect the merged result.

CRITICAL SAFETY RULES:
- NEVER include actions to turn off CRITICAL-priority devices (fridge plug, battery, sensors)
- The fridge (plug_kitchen_fridge) is ALWAYS critical — NEVER turn it off

DEVICE ACTION REFERENCE:
- light: "on" (params: {{"brightness": 0-100}}), "off", "dim" (params: {{"brightness": 0-100}})
- thermostat: "set_temperature" (params: {{"temperature": 60-85}}), "set_mode" (params: {{"mode": "heat|cool|auto|eco|off"}})
- smart_plug: "on", "off"
- lock: "lock", "unlock"
- coffee_maker: "on" (standby), "brew" (params: {{"strength": "light|medium|strong"}}), "off"
- battery: "set_mode" (params: {{"mode": "charge|discharge|auto|backup"}})

Respond with ONLY valid JSON:
{{
    "display_name": "Updated pattern name",
    "description": "Updated description reflecting all actions",
    "actions": [
        {{"device_id": "exact_device_id", "action": "action_name", "parameters": {{}}, "delay_seconds": 0}}
    ]
}}"""


class PatternDetectorAgent(BaseAgent):
    """Learns and detects patterns from user behavior and device events.

    Patterns are persisted to SQLite and loaded on startup.
    """

    def __init__(self):
        super().__init__("pattern_detector", "Pattern Detector Agent")
        self._detected_patterns: dict[str, DetectedPattern] = {}
        self._event_buffer: list[dict[str, Any]] = []
        self._analysis_task: asyncio.Task | None = None
        self._preference_tracker: dict[str, list[dict]] = defaultdict(list)

    @property
    def patterns(self) -> dict[str, DetectedPattern]:
        return self._detected_patterns

    # ------------------------------------------------------------------
    # Lifecycle — load patterns on start, persist on every change
    # ------------------------------------------------------------------

    async def start(self) -> None:
        await super().start()
        await chroma_store.initialize()
        await self._load_persisted_patterns()
        self._analysis_task = asyncio.create_task(self._periodic_analysis())

    async def stop(self) -> None:
        if self._analysis_task:
            self._analysis_task.cancel()
            try:
                await self._analysis_task
            except asyncio.CancelledError:
                pass
        await super().stop()

    async def _load_persisted_patterns(self) -> None:
        """Load all patterns from SQLite on startup."""
        try:
            rows = await event_store.load_all_patterns()
            loaded = 0
            for row_data in rows:
                try:
                    pattern = DetectedPattern.from_persist_dict(row_data)
                    self._detected_patterns[pattern.pattern_id] = pattern
                    loaded += 1
                except Exception as e:
                    logger.warning(f"Failed to deserialize pattern: {e}")

            if loaded:
                logger.info(f"Loaded {loaded} persisted patterns from database")
                # Broadcast to frontend so UI picks them up immediately
                for pattern in self._detected_patterns.values():
                    await ws_manager.broadcast("pattern_loaded", {
                        "pattern_id": pattern.pattern_id,
                        "type": pattern.pattern_type.value,
                        "name": pattern.display_name,
                        "description": pattern.description,
                        "confidence": pattern.confidence,
                        "frequency": pattern.frequency,
                        "approved": pattern.approved,
                        "actions": [a.model_dump() for a in pattern.action_sequence],
                        "trigger_conditions": pattern.trigger_conditions,
                    })
        except Exception as e:
            logger.error(f"Error loading persisted patterns: {e}")

    async def _persist_pattern(self, pattern: DetectedPattern) -> None:
        """Save a single pattern to SQLite."""
        try:
            await event_store.save_pattern(
                pattern_id=pattern.pattern_id,
                pattern_data=pattern.to_persist_dict(),
            )
        except Exception as e:
            logger.error(f"Failed to persist pattern {pattern.pattern_id}: {e}")

    # ------------------------------------------------------------------
    # Event logging
    # ------------------------------------------------------------------

    async def log_device_event(
        self,
        device_id: str,
        action: str,
        params: dict = {},
        source: str = "user",
    ) -> None:
        """Log a device event for pattern analysis."""
        event_id = str(uuid.uuid4())[:8]
        now = datetime.now()

        event_data = {
            "device_id": device_id,
            "action": action,
            "parameters": params,
            "source": source,
            "hour": now.hour,
            "minute": now.minute,
            "day_of_week": now.strftime("%a").lower(),
            "timestamp": now.isoformat(),
        }

        self._event_buffer.append(event_data)

        # Store in ChromaDB
        await chroma_store.add_event(
            event_id=event_id,
            device_id=device_id,
            action=action,
            metadata={
                "hour": str(now.hour),
                "day_of_week": now.strftime("%a").lower(),
                "source": source,
            },
        )

        # Track preference adjustments (skip the "user" pseudo-device from command logging)
        if source == "user" and device_id != "user":
            self._preference_tracker[device_id].append(event_data)

    # ------------------------------------------------------------------
    # User-defined pattern learning
    # ------------------------------------------------------------------

    def _find_matching_user_pattern(self, trigger_type: str, trigger_value: str) -> DetectedPattern | None:
        """Find an existing USER_DEFINED pattern with the same trigger for merging."""
        for pattern in self._detected_patterns.values():
            if pattern.pattern_type != PatternType.USER_DEFINED:
                continue
            tc = pattern.trigger_conditions
            if tc.get("type") == trigger_type and tc.get("value") == trigger_value:
                return pattern
        return None

    async def learn_user_preference(
        self,
        user_message: str,
        device_inventory: str,
    ) -> dict[str, Any]:
        """Parse a user's natural language preference into a structured pattern and persist it.

        If a user-defined pattern already exists for the same trigger (e.g. same
        calendar mode), the new instruction is MERGED into the existing pattern
        rather than creating a duplicate.

        Args:
            user_message: The user's raw assertion (e.g. "When I have a meeting, turn on office light")
            device_inventory: Current device inventory text (for LLM context)

        Returns:
            dict with 'success', 'pattern_id', and 'description'
        """
        try:
            # Step 1: Parse the new preference
            result = await llm_client.chat_json(
                messages=[{"role": "user", "content": PREFERENCE_PARSING_PROMPT.format(
                    device_inventory=device_inventory,
                    user_message=user_message,
                )}],
                temperature=0.2,
            )

            if "error" in result and "actions" not in result:
                logger.warning(f"LLM failed to parse preference: {result.get('error')}")
                return {"success": False, "error": "Could not understand the preference"}

            trigger_type = result.get("trigger_type", "")
            trigger_value = result.get("trigger_value", "")

            if not result.get("actions"):
                return {"success": False, "error": "No device actions could be identified"}

            # Step 2: Check for existing pattern with the same trigger → merge
            existing = self._find_matching_user_pattern(trigger_type, trigger_value)

            if existing:
                return await self._update_existing_pattern(
                    existing, user_message, device_inventory,
                )

            # Step 3: No existing pattern — create a new one
            return await self._create_new_pattern(result, user_message, trigger_type, trigger_value)

        except Exception as e:
            logger.error(f"Learn preference error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _create_new_pattern(
        self,
        parsed: dict[str, Any],
        user_message: str,
        trigger_type: str,
        trigger_value: str,
    ) -> dict[str, Any]:
        """Create a brand-new user-defined pattern."""
        display_name = parsed.get("display_name", "User Preference")
        description = parsed.get("description", user_message)
        actions_data = parsed.get("actions", [])

        # Filter out actions targeting critical devices (safety net)
        CRITICAL_DEVICE_IDS = {"plug_kitchen_fridge", "battery_main"}
        actions = []
        for a in actions_data:
            did = a.get("device_id", "")
            act = a.get("action", "")
            # Never turn off fridge
            if did in CRITICAL_DEVICE_IDS and act == "off":
                logger.warning(f"Blocked critical device action in pattern: {did}.{act}")
                continue
            try:
                actions.append(PatternAction(
                    device_id=did,
                    action=act,
                    parameters=a.get("parameters", {}),
                    delay_seconds=a.get("delay_seconds", 0),
                ))
            except Exception:
                continue

        if not actions:
            return {"success": False, "error": "No safe device actions could be identified"}

        pid = f"user_{uuid.uuid4().hex[:8]}"
        pattern = DetectedPattern(
            pattern_id=pid,
            pattern_type=PatternType.USER_DEFINED,
            display_name=display_name,
            description=description,
            frequency=1,
            confidence=1.0,
            trigger_conditions={"type": trigger_type, "value": trigger_value},
            action_sequence=actions,
            approved=True,
            source_utterance=user_message,
        )

        self._detected_patterns[pid] = pattern
        await self._persist_pattern(pattern)

        await ws_manager.broadcast("pattern_learned", {
            "pattern_id": pid,
            "type": pattern.pattern_type.value,
            "name": display_name,
            "description": description,
            "trigger": pattern.trigger_conditions,
            "actions": [a.model_dump() for a in actions],
            "source_utterance": user_message,
        })

        logger.info(
            f"Learned NEW preference '{display_name}': "
            f"trigger={trigger_type}:{trigger_value}, {len(actions)} actions"
        )

        return {
            "success": True,
            "pattern_id": pid,
            "display_name": display_name,
            "description": description,
            "trigger": pattern.trigger_conditions,
            "actions_count": len(actions),
            "merged": False,
        }

    async def _update_existing_pattern(
        self,
        existing: DetectedPattern,
        user_message: str,
        device_inventory: str,
    ) -> dict[str, Any]:
        """Merge a new user instruction into an existing pattern with the same trigger."""
        logger.info(
            f"Found existing pattern '{existing.display_name}' ({existing.pattern_id}) "
            f"for trigger {existing.trigger_conditions} — merging"
        )

        # Format existing actions for the merge prompt
        existing_actions_text = "\n".join(
            f"    - {a.device_id}.{a.action}({a.parameters})"
            for a in existing.action_sequence
        ) or "    (none)"

        prompt = PREFERENCE_UPDATE_PROMPT.format(
            existing_name=existing.display_name,
            existing_description=existing.description,
            existing_trigger_type=existing.trigger_conditions.get("type", ""),
            existing_trigger_value=existing.trigger_conditions.get("value", ""),
            existing_actions=existing_actions_text,
            device_inventory=device_inventory,
            user_message=user_message,
        )

        result = await llm_client.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        if "error" in result and "actions" not in result:
            logger.warning(f"LLM merge failed: {result.get('error')}")
            return {"success": False, "error": "Could not merge the preference update"}

        new_actions_data = result.get("actions", [])
        new_display_name = result.get("display_name", existing.display_name)
        new_description = result.get("description", existing.description)

        # Filter out critical device shutoffs
        CRITICAL_DEVICE_IDS = {"plug_kitchen_fridge", "battery_main"}
        new_actions = []
        for a in new_actions_data:
            did = a.get("device_id", "")
            act = a.get("action", "")
            if did in CRITICAL_DEVICE_IDS and act == "off":
                logger.warning(f"Blocked critical device action in merge: {did}.{act}")
                continue
            try:
                new_actions.append(PatternAction(
                    device_id=did,
                    action=act,
                    parameters=a.get("parameters", {}),
                    delay_seconds=a.get("delay_seconds", 0),
                ))
            except Exception:
                continue

        if not new_actions:
            return {"success": False, "error": "No safe actions after merge"}

        # Update in-place
        existing.display_name = new_display_name
        existing.description = new_description
        existing.action_sequence = new_actions
        existing.source_utterance = (
            (existing.source_utterance or "") + " | " + user_message
        )
        existing.last_occurrence = datetime.now()

        await self._persist_pattern(existing)

        await ws_manager.broadcast("pattern_updated", {
            "pattern_id": existing.pattern_id,
            "type": existing.pattern_type.value,
            "name": new_display_name,
            "description": new_description,
            "trigger": existing.trigger_conditions,
            "actions": [a.model_dump() for a in new_actions],
            "source_utterance": existing.source_utterance,
        })

        logger.info(
            f"MERGED preference '{new_display_name}' ({existing.pattern_id}): "
            f"now {len(new_actions)} actions"
        )

        return {
            "success": True,
            "pattern_id": existing.pattern_id,
            "display_name": new_display_name,
            "description": new_description,
            "trigger": existing.trigger_conditions,
            "actions_count": len(new_actions),
            "merged": True,
        }

    def get_matching_patterns(
        self,
        trigger_type: str,
        trigger_value: str,
    ) -> list[DetectedPattern]:
        """Find all approved patterns that match a given trigger.

        Used by the orchestrator to look up user-defined rules before planning
        actions for a mode change, location change, etc.
        """
        matches = []
        for pattern in self._detected_patterns.values():
            if not pattern.approved:
                continue
            tc = pattern.trigger_conditions
            if tc.get("type") == trigger_type and tc.get("value") == trigger_value:
                matches.append(pattern)
        return matches

    def get_global_constraints(self) -> list[DetectedPattern]:
        """Return all approved 'global' constraint patterns.

        These are rules that apply AT ALL TIMES (e.g. "never unlock the door",
        "never turn off the fridge") and should be injected into every LLM prompt
        and enforced at execution time.
        """
        return [
            p for p in self._detected_patterns.values()
            if p.approved and p.trigger_conditions.get("type") == "global"
        ]

    def get_all_approved_patterns(self) -> list[DetectedPattern]:
        """Return all approved patterns — contextual and global."""
        return [p for p in self._detected_patterns.values() if p.approved]

    # ------------------------------------------------------------------
    # Periodic analysis (existing — now with persistence)
    # ------------------------------------------------------------------

    async def run(self, *args, **kwargs) -> list[DetectedPattern]:
        """Analyze accumulated events for patterns."""
        self._status = AgentStatus.RUNNING

        try:
            # Get all events from ChromaDB
            all_events = await chroma_store.get_all_events()
            if len(all_events) < 5:
                self._status = AgentStatus.IDLE
                return list(self._detected_patterns.values())

            # Format events for LLM analysis
            events_text = self._format_events_for_analysis(all_events)

            # Use LLM to detect patterns
            patterns = await self._llm_pattern_detection(events_text)

            # Also run rule-based detection
            rule_patterns = self._rule_based_detection()

            # Merge patterns
            for p in rule_patterns:
                if p.pattern_id not in self._detected_patterns:
                    patterns.append(p)

            # Update stored patterns
            for pattern in patterns:
                existing = self._detected_patterns.get(pattern.pattern_id)
                if existing:
                    existing.frequency = max(existing.frequency, pattern.frequency)
                    existing.confidence = max(existing.confidence, pattern.confidence)
                    existing.last_occurrence = datetime.now()
                    await self._persist_pattern(existing)
                else:
                    self._detected_patterns[pattern.pattern_id] = pattern
                    await self._persist_pattern(pattern)

                    # Store in ChromaDB (for vector search)
                    await chroma_store.add_pattern(
                        pattern_id=pattern.pattern_id,
                        description=pattern.description,
                        metadata={
                            "type": pattern.pattern_type.value,
                            "frequency": str(pattern.frequency),
                            "confidence": str(pattern.confidence),
                        },
                    )

            # Notify about new ready-to-suggest patterns
            for pattern in self._detected_patterns.values():
                if pattern.is_ready_to_suggest() and not pattern.approved:
                    await ws_manager.broadcast("pattern_suggestion", {
                        "pattern_id": pattern.pattern_id,
                        "type": pattern.pattern_type.value,
                        "name": pattern.display_name,
                        "description": pattern.description,
                        "confidence": pattern.confidence,
                        "frequency": pattern.frequency,
                        "actions": [a.model_dump() for a in pattern.action_sequence],
                    })

                    await mqtt_client.publish(Topics.PATTERN_DETECTED, {
                        "pattern_id": pattern.pattern_id,
                        "description": pattern.description,
                    })

            self._record_action(
                action=f"Detected {len(self._detected_patterns)} patterns",
                reasoning=f"Analyzed {len(all_events)} events",
            )

            self._status = AgentStatus.IDLE
            return list(self._detected_patterns.values())

        except Exception as e:
            logger.error(f"Pattern detection error: {e}", exc_info=True)
            self._status = AgentStatus.ERROR
            self._error = str(e)
            return []

    async def _periodic_analysis(self) -> None:
        """Run pattern analysis periodically."""
        try:
            while True:
                await asyncio.sleep(300)  # Every 5 minutes
                if len(self._event_buffer) >= 5:
                    await self.run()
        except asyncio.CancelledError:
            pass

    def _format_events_for_analysis(self, events: list[dict]) -> str:
        """Format events for LLM analysis."""
        lines = []
        for e in events[-100:]:  # Last 100 events
            meta = e.get("metadata", {})
            lines.append(
                f"[{meta.get('day_of_week', '?')} {meta.get('hour', '?')}:00] "
                f"{meta.get('device_id', '?')} -> {meta.get('action', '?')} "
                f"(source: {meta.get('source', '?')})"
            )
        return "\n".join(lines)

    async def _llm_pattern_detection(self, events_text: str) -> list[DetectedPattern]:
        """Use LLM to detect patterns in events."""
        try:
            result = await llm_client.chat_json(
                messages=[{
                    "role": "user",
                    "content": PATTERN_ANALYSIS_PROMPT.format(events=events_text),
                }],
                temperature=0.2,
            )

            patterns = []
            for p_data in result.get("patterns", []):
                pid = f"pattern_{uuid.uuid4().hex[:6]}"
                try:
                    pattern = DetectedPattern(
                        pattern_id=pid,
                        pattern_type=PatternType(p_data.get("type", "routine")),
                        display_name=p_data.get("name", "Unknown Pattern"),
                        description=p_data.get("description", ""),
                        frequency=int(p_data.get("frequency", 1)),
                        confidence=float(p_data.get("confidence", 0.5)),
                        trigger_conditions=p_data.get("trigger", {}),
                        action_sequence=[
                            PatternAction(**a) for a in p_data.get("actions", [])
                        ],
                    )
                    patterns.append(pattern)
                except Exception as e:
                    logger.warning(f"Failed to parse pattern: {e}")

            return patterns

        except Exception as e:
            logger.warning(f"LLM pattern detection failed: {e}")
            return []

    def _rule_based_detection(self) -> list[DetectedPattern]:
        """Simple rule-based pattern detection from event buffer."""
        patterns = []

        # Group events by hour and day
        time_device_actions: dict[str, list[dict]] = defaultdict(list)
        for event in self._event_buffer:
            key = f"{event.get('day_of_week', '')}_{event.get('hour', '')}"
            time_device_actions[key].append(event)

        # Find repeated time-based sequences
        sequence_counts: dict[str, int] = defaultdict(int)
        for key, events in time_device_actions.items():
            if len(events) >= 2:
                seq = tuple(
                    (e["device_id"], e["action"]) for e in sorted(events, key=lambda x: x.get("timestamp", ""))
                )
                seq_key = str(seq)
                sequence_counts[seq_key] += 1

                if sequence_counts[seq_key] >= 2:
                    pid = f"routine_{hash(seq_key) % 10000:04d}"
                    if pid not in self._detected_patterns:
                        actions = [
                            PatternAction(device_id=d, action=a)
                            for d, a in seq
                        ]
                        patterns.append(DetectedPattern(
                            pattern_id=pid,
                            pattern_type=PatternType.ROUTINE,
                            display_name=f"Routine at {events[0].get('hour', '?')}:00",
                            description=f"Repeated sequence: {' -> '.join(f'{d}.{a}' for d, a in seq)}",
                            frequency=sequence_counts[seq_key],
                            confidence=min(0.5 + sequence_counts[seq_key] * 0.15, 1.0),
                            trigger_conditions={"hour": events[0].get("hour")},
                            action_sequence=actions,
                        ))

        # Detect preference patterns from user adjustments
        for device_id, adjustments in self._preference_tracker.items():
            if len(adjustments) >= 3:
                pid = f"pref_{device_id}_{hash(str(adjustments)) % 10000:04d}"
                patterns.append(DetectedPattern(
                    pattern_id=pid,
                    pattern_type=PatternType.PREFERENCE,
                    display_name=f"User preference for {device_id}",
                    description=f"User frequently adjusts {device_id} ({len(adjustments)} times)",
                    frequency=len(adjustments),
                    confidence=min(0.4 + len(adjustments) * 0.1, 1.0),
                ))

        return patterns

    # ------------------------------------------------------------------
    # Approve / dismiss (now persisted)
    # ------------------------------------------------------------------

    async def approve_pattern(self, pattern_id: str) -> bool:
        """Approve a detected pattern for automation."""
        pattern = self._detected_patterns.get(pattern_id)
        if pattern:
            pattern.approved = True
            await self._persist_pattern(pattern)
            await ws_manager.broadcast("pattern_approved", {"pattern_id": pattern_id})
            return True
        return False

    async def dismiss_pattern(self, pattern_id: str) -> bool:
        """Dismiss a detected pattern (removes from memory and database)."""
        if pattern_id in self._detected_patterns:
            del self._detected_patterns[pattern_id]
            await event_store.delete_pattern(pattern_id)
            await ws_manager.broadcast("pattern_dismissed", {"pattern_id": pattern_id})
            return True
        return False


# Singleton
pattern_agent = PatternDetectorAgent()
