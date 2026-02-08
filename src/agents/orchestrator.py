"""Orchestrator Agent -- coordinates all agents, uses LLM for dynamic action planning.

Includes pattern-aware constraint enforcement at execution time.
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime
from typing import Any

from config import settings
from src.agents.base import BaseAgent, AgentStatus
from src.agents.home_state import home_state_agent
from src.agents.threat_assessment import threat_agent
from src.agents.voice import voice_agent
from src.agents.pattern_detector import pattern_agent
from src.agents.user_info import user_info_agent
from src.integrations.openrouter import llm_client
from src.models.threat import ThreatLevel
from src.models.device import DeviceType, PriorityTier
from src.devices.registry import device_registry
from src.storage.event_store import event_store
from src.models.events import Event, EventType
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)

# Recognised home modes (in priority order for conflict resolution)
HOME_MODES = ("normal", "active", "preparing_for_meeting", "focus", "do_not_disturb", "sleep")

# ---------------------------------------------------------------------------
# Prompt: general user commands (e.g. "set up my house for bedtime")
# ---------------------------------------------------------------------------
ORCHESTRATOR_PROMPT = """You are the central orchestrator for a smart home system.
You coordinate multiple agents to make intelligent decisions.

CURRENT CONTEXT:
- Threat Assessment: {threat_summary}
- User Location: {user_location}
- Calendar: {calendar_context}
- Energy: {energy_summary}
- Active Patterns: {patterns}

ALL AVAILABLE DEVICES:
{device_inventory}

REQUEST: {request}

Device action reference:
- light: "on" (params: {{"brightness": 0-100}}), "off", "dim" (params: {{"brightness": 0-100}}), "color" (params: {{"r": 0-255, "g": 0-255, "b": 0-255}})
- thermostat: "set_temperature" (params: {{"temperature": 60-85}}), "set_mode" (params: {{"mode": "heat|cool|auto|eco|off"}}), "eco_mode"
- smart_plug: "on", "off"
- lock: "lock", "unlock"
- coffee_maker: "brew" (params: {{"strength": "light|medium|strong"}}), "off", "keep_warm"
- battery: "set_mode" (params: {{"mode": "charge|discharge|auto|backup"}})
- sensor: read-only, no actions

CRITICAL RULES:
1. ONLY produce actions if the request CLEARLY relates to controlling home devices, environment, or matches a known pattern.
2. If the request is random words, unrelated to smart home control, or you cannot determine a meaningful action, return an EMPTY actions list and set "not_understood" to true.
3. Do NOT hallucinate or guess actions for nonsensical requests. When in doubt, return no actions.
4. Check active patterns — if the request matches a pattern name or keyword (e.g. "movie" matches "Movie Mode"), execute that pattern's actions.

Respond with ONLY valid JSON:
{{
    "reasoning": "Why these actions are needed (or why the request is not understood)",
    "actions": [
        {{
            "device_id": "exact_device_id",
            "action": "action_name",
            "parameters": {{}}
        }}
    ],
    "alert_message": "Optional voice message to user",
    "require_permission": false,
    "not_understood": false
}}"""

# ---------------------------------------------------------------------------
# Prompt: LLM-based threat response planning (replaces hardcoded handlers)
# ---------------------------------------------------------------------------
THREAT_RESPONSE_PROMPT = """You are the smart home orchestrator. A threat has been detected.
Analyze the threat and decide EXACTLY which devices to adjust. Be comprehensive.

THREAT:
- Level: {threat_level}
- Type: {threat_type}
- Summary: {threat_summary}
- Reasoning: {threat_reasoning}

USER LOCATION: {user_location}

ALL AVAILABLE DEVICES (current state):
{device_inventory}

RULES:
1. NEVER turn off CRITICAL-priority devices. Specifically: plug_kitchen_fridge (fridge) must NEVER be turned off. Battery and sensors must not be turned off.
2. Locks may only be locked (not unlocked) during threats.
3. Be comprehensive — adjust ALL relevant devices, not just one or two.
4. Use the EXACT device_id values shown above.
4. For heat_wave: set thermostats to cool mode at 68°F, turn off non-essential lights and plugs (low/medium priority), charge battery.
5. For grid_strain: set thermostats to eco mode, turn off ALL low-priority and medium-priority lights/plugs, switch battery to backup.
6. For cold_snap: set thermostats to heat mode at 72°F, charge battery.
7. For storm: lock all doors, switch battery to backup, turn off low-priority devices.
8. For power_outage: switch battery to backup, turn off ALL non-essential devices.
9. Always include thermostat adjustments AND non-essential device shutoffs when threat is HIGH or CRITICAL.

DEVICE ACTION REFERENCE:
- light: "on" (params: {{"brightness": 0-100}}), "off" (no params), "dim" (params: {{"brightness": 0-100}})
- thermostat: "set_temperature" (params: {{"temperature": 60-85}}), "set_mode" (params: {{"mode": "heat|cool|auto|eco|off"}}), "eco_mode" (no params)
- smart_plug: "on" (no params), "off" (no params)
- lock: "lock" (no params), "unlock" (no params)
- coffee_maker: "brew" (params: {{"strength": "light|medium|strong"}}), "off" (no params)
- battery: "set_mode" (params: {{"mode": "charge|discharge|auto|backup"}})
- sensor: READ ONLY — no actions

Respond with ONLY valid JSON:
{{
    "reasoning": "Brief explanation of why these specific actions",
    "actions": [
        {{"device_id": "exact_id", "action": "action_name", "parameters": {{}}}}
    ]
}}"""

# ---------------------------------------------------------------------------
# Prompt: LLM-based GPS / location response
# ---------------------------------------------------------------------------
LOCATION_RESPONSE_PROMPT = """You are the smart home orchestrator. The user's GPS location has changed.
Decide which devices to adjust based on the new location and current device states.

NEW LOCATION: {current_location}

ALL AVAILABLE DEVICES (current state):
{device_inventory}

RULES BY LOCATION:
- AWAY: Lock all doors. Turn off ALL lights. Turn off non-essential smart plugs (but NOT the fridge — it is critical). Turn off coffee maker. Set all thermostats to eco mode.
- LEAVING: Lock front door. Turn off non-essential lights. Set thermostats to eco mode.
- ARRIVING: Unlock front door. Turn on living room and kitchen main lights (brightness 80). Set thermostats to 72°F auto mode.
- HOME: Ensure comfortable settings — main lights on (brightness 80), thermostat at 72°F auto.

CRITICAL: NEVER turn off plug_kitchen_fridge (the fridge) — it is critical. Never turn off sensors or battery.

DEVICE ACTION REFERENCE:
- light: "on" (params: {{"brightness": 0-100}}), "off" (no params)
- thermostat: "set_temperature" (params: {{"temperature": 60-85}}), "set_mode" (params: {{"mode": "heat|cool|auto|eco|off"}}), "eco_mode" (no params)
- smart_plug: "on" (no params), "off" (no params)  — but NOT plug_kitchen_fridge
- lock: "lock" (no params), "unlock" (no params)
- coffee_maker: "on" (standby), "off" (no params), "brew" (params: {{"strength": "medium"}})
- battery: "set_mode" (params: {{"mode": "charge|discharge|auto|backup"}})

Respond with ONLY valid JSON:
{{
    "reasoning": "Brief explanation",
    "actions": [
        {{"device_id": "exact_id", "action": "action_name", "parameters": {{}}}}
    ]
}}"""

# ---------------------------------------------------------------------------
# Prompt: LLM-based calendar / home-mode response
# ---------------------------------------------------------------------------
CALENDAR_RESPONSE_PROMPT = """You are the smart home orchestrator. The home mode has changed based on the user's calendar.
Decide EXACTLY which devices to adjust for the new mode. Be comprehensive but reasonable.

NEW MODE: {new_mode}
PREVIOUS MODE: {old_mode}
CALENDAR CONTEXT: {calendar_context}
USER LOCATION: {user_location}
CURRENT TIME: {current_time}

ALL AVAILABLE DEVICES (current state):
{device_inventory}

MODE GUIDELINES:

1. **preparing_for_meeting** (meeting starts in a few minutes):
   - Turn on office light at brightness 80
   - Set office thermostat to comfortable (72°F, auto)
   - Dim non-office lights to 30 (living room, bedroom) — user is transitioning
   - Turn off any noisy devices (coffee maker if done, non-essential plugs)
   - Ensure front door is locked (minimise interruptions)

2. **do_not_disturb** (currently in meeting/call):
   - Office light at brightness 70 (stable, no changes mid-meeting)
   - Turn OFF all non-office lights to avoid distractions
   - Set non-office thermostats to eco mode
   - Ensure all doors are locked
   - Turn off coffee maker and non-essential plugs

3. **focus** (deep work / study):
   - Similar to do_not_disturb but allow bedroom light at low (20)
   - Office light at 90
   - Comfortable thermostat

4. **sleep**:
   - Turn off ALL lights
   - Lock all doors
   - Lower thermostat to 68°F
   - Turn off all non-essential devices

5. **active** (workout / exercise):
   - Living room or relevant room lights bright (90)
   - Comfortable temperature (70°F)

6. **normal** (restore after any special mode):
   - Restore lights to comfortable levels (living room 80, bedroom 60, office 50, kitchen 80)
   - Set thermostats to auto at 72°F
   - Unlock front door if user is home

CRITICAL: Use EXACT device_id values from the inventory. Never modify sensors or battery. NEVER turn off plug_kitchen_fridge (the fridge).

DEVICE ACTION REFERENCE:
- light: "on" (params: {{"brightness": 0-100}}), "off" (no params), "dim" (params: {{"brightness": 0-100}})
- thermostat: "set_temperature" (params: {{"temperature": 60-85}}), "set_mode" (params: {{"mode": "heat|cool|auto|eco|off"}}), "eco_mode" (no params)
- smart_plug: "on" (no params), "off" (no params) — but NOT plug_kitchen_fridge
- lock: "lock" (no params), "unlock" (no params)
- coffee_maker: "on" (standby), "off" (no params), "brew" (params: {{"strength": "medium"}})
- battery: "set_mode" (params: {{"mode": "charge|discharge|auto|backup"}})

Respond with ONLY valid JSON:
{{
    "reasoning": "Brief explanation of why these adjustments for this mode",
    "actions": [
        {{"device_id": "exact_id", "action": "action_name", "parameters": {{}}}}
    ],
    "voice_message": "Short friendly message to inform the user about the mode change (1 sentence)"
}}"""


class OrchestratorAgent(BaseAgent):
    """Central coordinator that orchestrates all agents."""

    def __init__(self):
        super().__init__("orchestrator", "Orchestrator Agent")
        self._decision_history: list[dict[str, Any]] = []
        self._monitoring_task: asyncio.Task | None = None
        self._last_location_handled: str | None = None
        # Calendar / home-mode tracking
        self._current_home_mode: str = "normal"
        self._pre_mode_device_snapshot: dict[str, dict[str, Any]] | None = None

    @property
    def decision_history(self) -> list[dict[str, Any]]:
        return self._decision_history[-50:]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        await super().start()
        await home_state_agent.start()
        await threat_agent.start()
        await voice_agent.start()
        await pattern_agent.start()
        await user_info_agent.start()
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Orchestrator started with all sub-agents")

    async def stop(self) -> None:
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        await pattern_agent.stop()
        await user_info_agent.stop()
        await voice_agent.stop()
        await threat_agent.stop()
        await home_state_agent.stop()
        await super().stop()

    # ------------------------------------------------------------------
    # Monitoring loop
    # ------------------------------------------------------------------

    async def _monitoring_loop(self) -> None:
        """Continuously monitor conditions and react."""
        try:
            while True:
                await asyncio.sleep(10)
                await self._check_and_respond()
        except asyncio.CancelledError:
            pass

    async def _check_and_respond(self) -> None:
        """Check current conditions and respond if needed.

        Priority order:
        1. Threats (safety-critical)
        2. Calendar / home-mode transitions
        3. Location changes
        4. Pattern suggestions (future)
        """
        # --- 1. Threat level check ---
        assessment = threat_agent.latest_assessment
        if assessment.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            await self._handle_threat(assessment)

        # --- 2. Calendar context / home-mode transitions ---
        await self._handle_calendar_context()

        # --- 3. Location check (dedup handled inside handle_location_change) ---
        location = user_info_agent.location.value
        if location in ("away", "leaving"):
            await self.handle_location_change(location)

        # --- 4. Pattern check (future) ---
        for pattern in pattern_agent.patterns.values():
            if pattern.approved and pattern.is_ready_to_suggest():
                pass

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _build_device_inventory(self) -> str:
        """Build a text description of all devices with their current states and capabilities."""
        lines = []
        for room_id, device_ids in device_registry.rooms.items():
            lines.append(f"\n[{room_id}]")
            for device_id in device_ids:
                device = device_registry.get_device(device_id)
                if not device:
                    continue
                state = device.state
                caps = ", ".join(device.capabilities)
                props_parts = []
                for k, v in state.properties.items():
                    props_parts.append(f"{k}={v}")
                props_str = ", ".join(props_parts) if props_parts else "none"
                lines.append(
                    f"  {device_id} ({device.display_name})"
                    f" | type={device.device_type.value}"
                    f" | power={'ON' if state.power else 'OFF'}"
                    f" | online={'yes' if device.is_online else 'no'}"
                    f" | priority={state.priority_tier.value}"
                    f" | {state.current_watts}W"
                    f" | caps=[{caps}]"
                    f" | state: {props_str}"
                )
        return "\n".join(lines)

    # Device IDs that must never be turned off by any automated plan
    _PROTECTED_DEVICE_IDS = {"plug_kitchen_fridge"}

    async def _execute_action_plan(self, actions: list[dict]) -> tuple[list[str], list[str]]:
        """Execute a list of device actions from an LLM-generated plan.

        Before executing, checks:
        1. Hardcoded protections (e.g. plug_kitchen_fridge must never be turned off)
        2. User-defined global constraints (e.g. "never unlock the door")
        """
        executed: list[str] = []
        failed: list[str] = []

        # Build a dynamic block-list from user-defined global constraint patterns
        pattern_blocked = self._get_blocked_actions_from_patterns()
        if pattern_blocked:
            logger.debug(f"Pattern-blocked actions: {pattern_blocked}")

        for action in actions:
            device_id = action.get("device_id", "")
            action_name = action.get("action", "")
            parameters = action.get("parameters") or {}

            if not device_id or not action_name:
                failed.append(f"Invalid action spec: {action}")
                continue

            # Hard safety: never turn off protected devices regardless of LLM output
            if device_id in self._PROTECTED_DEVICE_IDS and action_name == "off":
                logger.warning(f"BLOCKED turning off protected device: {device_id}")
                failed.append(f"{device_id}.off: BLOCKED (critical device)")
                continue

            # User-defined constraint enforcement
            if device_id in pattern_blocked and action_name in pattern_blocked[device_id]:
                logger.warning(
                    f"BLOCKED by user constraint: {device_id}.{action_name} "
                    f"(global pattern prohibits this action)"
                )
                failed.append(f"{device_id}.{action_name}: BLOCKED (user constraint)")
                continue

            try:
                result = await home_state_agent.execute_action(
                    device_id, action_name, parameters
                )
                if result.get("success"):
                    desc = f"{device_id}.{action_name}"
                    if parameters:
                        desc += f"({parameters})"
                    executed.append(desc)
                    logger.info(f"✓ {desc}")
                else:
                    error = result.get("error", "unknown")
                    failed.append(f"{device_id}.{action_name}: {error}")
                    logger.warning(f"✗ {device_id}.{action_name}: {error}")
            except Exception as e:
                failed.append(f"{device_id}.{action_name}: {e}")
                logger.error(f"✗ {device_id}.{action_name} exception: {e}")

        return executed, failed

    # ------------------------------------------------------------------
    # Threat handling
    # ------------------------------------------------------------------

    async def _handle_threat(self, assessment) -> None:
        """Handle a detected threat — voice alert, then execute if approved."""
        threat_key = f"{assessment.threat_type.value}_{assessment.threat_level.value}"

        # Avoid duplicate handling
        recent_decisions = [d.get("threat_key") for d in self._decision_history[-5:]]
        if threat_key in recent_decisions:
            return

        logger.info(f"Handling threat: {assessment.summary}")

        needs_permission = assessment.requires_user_permission()

        # Voice alert with natural language script
        voice_result = await voice_agent.run(
            message=assessment.summary,
            require_permission=needs_permission,
            threat_summary=assessment.summary,
            threat_level=assessment.threat_level.value,
            actions=assessment.recommended_actions[:4],
        )

        if needs_permission:
            approved = voice_result.get("approved", False)
            if approved:
                logger.info("User approved threat response — executing actions")
                await self._execute_threat_response(assessment)
            else:
                logger.info("User denied threat response actions")
        else:
            await self._execute_threat_response(assessment)

        self._decision_history.append({
            "threat_key": threat_key,
            "assessment": assessment.summary,
            "actions_executed": voice_result.get("approved", not needs_permission),
            "timestamp": assessment.timestamp.isoformat(),
        })

    async def _execute_threat_response(self, assessment) -> None:
        """Use LLM to dynamically plan and execute threat response based on all available devices."""
        device_inventory = self._build_device_inventory()

        # Look up user-defined patterns for this threat type
        user_patterns_text = self._format_user_patterns("threat", assessment.threat_type.value)

        prompt = THREAT_RESPONSE_PROMPT.format(
            threat_level=assessment.threat_level.value,
            threat_type=assessment.threat_type.value,
            threat_summary=assessment.summary,
            threat_reasoning=assessment.reasoning,
            device_inventory=device_inventory,
            user_location=user_info_agent.location.value,
        )

        # Inject global constraints (always-on rules)
        global_constraints = self._format_global_constraints()
        if global_constraints:
            prompt += (
                "\n\n⚠ MANDATORY USER RULES (these override all other guidelines — "
                "violating these is FORBIDDEN):\n"
                f"{global_constraints}"
            )

        if user_patterns_text != "None":
            prompt += (
                "\n\nCONTEXTUAL PREFERENCES (honour these for this threat):\n"
                f"{user_patterns_text}"
            )

        try:
            result = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            if "error" in result and "actions" not in result:
                logger.warning(f"LLM failed for threat response: {result.get('error')}")
                await self._fallback_threat_response(assessment)
                return

            reasoning = result.get("reasoning", "")
            actions = result.get("actions", [])

            logger.info(f"LLM planned {len(actions)} threat response actions: {reasoning}")

            executed, failed = await self._execute_action_plan(actions)

            logger.info(
                f"Threat response complete: {len(executed)} executed, {len(failed)} failed"
            )
            if failed:
                logger.warning(f"Failed actions: {failed}")

            await ws_manager.broadcast("orchestrator_action", {
                "type": "threat_response",
                "assessment": assessment.summary,
                "reasoning": reasoning,
                "actions_executed": executed,
                "actions_failed": failed,
            })

        except Exception as e:
            logger.error(f"LLM-based threat response failed: {e}", exc_info=True)
            await self._fallback_threat_response(assessment)

    async def _fallback_threat_response(self, assessment) -> None:
        """Rule-based fallback when LLM is unavailable for threat response."""
        executed: list[str] = []
        threat_type = assessment.threat_type.value
        pattern_blocked = self._get_blocked_actions_from_patterns()

        try:
            if threat_type == "heat_wave":
                # Pre-cool all thermostats
                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    await home_state_agent.execute_action(
                        device.device_id, "set_temperature", {"temperature": 68}
                    )
                    r = await home_state_agent.execute_action(
                        device.device_id, "set_mode", {"mode": "cool"}
                    )
                    if r.get("success"):
                        executed.append(f"{device.device_id}.cool(68)")

                # Turn off non-essential lights and plugs
                for device in device_registry.devices.values():
                    if (
                        device.state.priority_tier in (PriorityTier.LOW, PriorityTier.OPTIONAL)
                        and device.state.power
                        and device.device_type
                        not in (DeviceType.SENSOR, DeviceType.BATTERY, DeviceType.LOCK)
                    ):
                        if self._is_action_blocked(device.device_id, "off", pattern_blocked):
                            continue
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                # Charge battery
                r = await home_state_agent.execute_action(
                    "battery_main", "set_mode", {"mode": "charge"}
                )
                if r.get("success"):
                    executed.append("battery_main.charge")

            elif threat_type == "grid_strain":
                # Eco mode on thermostats
                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    r = await home_state_agent.execute_action(device.device_id, "eco_mode")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.eco_mode")

                # Turn off non-essential devices (low + medium priority)
                for device in device_registry.devices.values():
                    if (
                        device.state.priority_tier
                        in (PriorityTier.LOW, PriorityTier.OPTIONAL, PriorityTier.MEDIUM)
                        and device.state.power
                        and device.device_type
                        not in (DeviceType.THERMOSTAT, DeviceType.SENSOR, DeviceType.BATTERY, DeviceType.LOCK)
                    ):
                        if self._is_action_blocked(device.device_id, "off", pattern_blocked):
                            continue
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                # Battery backup
                r = await home_state_agent.execute_action(
                    "battery_main", "set_mode", {"mode": "backup"}
                )
                if r.get("success"):
                    executed.append("battery_main.backup")

            elif threat_type == "cold_snap":
                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    await home_state_agent.execute_action(
                        device.device_id, "set_temperature", {"temperature": 72}
                    )
                    r = await home_state_agent.execute_action(
                        device.device_id, "set_mode", {"mode": "heat"}
                    )
                    if r.get("success"):
                        executed.append(f"{device.device_id}.heat(72)")

                r = await home_state_agent.execute_action(
                    "battery_main", "set_mode", {"mode": "charge"}
                )
                if r.get("success"):
                    executed.append("battery_main.charge")

            elif threat_type in ("storm", "power_outage"):
                # Lock doors
                for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                    if self._is_action_blocked(device.device_id, "lock", pattern_blocked):
                        continue
                    r = await home_state_agent.execute_action(device.device_id, "lock")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.lock")

                # Battery backup
                r = await home_state_agent.execute_action(
                    "battery_main", "set_mode", {"mode": "backup"}
                )
                if r.get("success"):
                    executed.append("battery_main.backup")

                # Turn off non-essential devices
                for device in device_registry.devices.values():
                    if (
                        device.state.priority_tier in (PriorityTier.LOW, PriorityTier.OPTIONAL)
                        and device.state.power
                        and device.device_type
                        not in (DeviceType.SENSOR, DeviceType.BATTERY, DeviceType.LOCK)
                    ):
                        if self._is_action_blocked(device.device_id, "off", pattern_blocked):
                            continue
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

        except Exception as e:
            logger.error(f"Fallback threat response error: {e}", exc_info=True)

        logger.info(f"Fallback threat response: {len(executed)} actions executed")
        await ws_manager.broadcast("orchestrator_action", {
            "type": "threat_response_fallback",
            "actions_executed": executed,
        })

    # ------------------------------------------------------------------
    # Calendar / home-mode handling
    # ------------------------------------------------------------------

    @property
    def current_home_mode(self) -> str:
        return self._current_home_mode

    def _snapshot_device_states(self) -> dict[str, dict[str, Any]]:
        """Take a snapshot of current device states for later restoration."""
        snapshot: dict[str, dict[str, Any]] = {}
        for device_id, device in device_registry.devices.items():
            state = device.state
            snapshot[device_id] = {
                "power": state.power,
                "properties": dict(state.properties),
                "device_type": device.device_type.value,
            }
        return snapshot

    async def _handle_calendar_context(self) -> None:
        """Detect calendar-driven mode transitions and respond."""
        cal_ctx = user_info_agent.calendar_context
        suggested = cal_ctx.get("suggested_mode", "normal")

        # No change → nothing to do
        if suggested == self._current_home_mode:
            return

        old_mode = self._current_home_mode
        new_mode = suggested

        logger.info(f"Home mode transition: {old_mode} → {new_mode}")

        # ---- Snapshot before leaving normal mode ----
        if old_mode == "normal" and new_mode != "normal":
            self._pre_mode_device_snapshot = self._snapshot_device_states()
            logger.info("Saved device snapshot for later restoration")

        # ---- Enable/disable DND on voice agent ----
        if new_mode in ("do_not_disturb", "focus"):
            event_name = cal_ctx.get("current_event", cal_ctx.get("preparing_for", "event"))
            voice_agent.set_dnd_mode(True, reason=f"In {new_mode} for: {event_name}")
        elif old_mode in ("do_not_disturb", "focus") and new_mode not in ("do_not_disturb", "focus"):
            voice_agent.set_dnd_mode(False)

        # ---- Use LLM (or fallback) to plan device adjustments ----
        await self._execute_mode_transition(old_mode, new_mode, cal_ctx)

        # Update tracked mode
        self._current_home_mode = new_mode

        # ---- If we are returning to normal, clear the snapshot ----
        if new_mode == "normal":
            self._pre_mode_device_snapshot = None

        # Record decision
        self._decision_history.append({
            "threat_key": f"mode_{new_mode}",
            "assessment": f"Home mode: {old_mode} → {new_mode}",
            "actions_executed": True,
            "timestamp": datetime.now().isoformat(),
        })

        await ws_manager.broadcast("home_mode_change", {
            "previous_mode": old_mode,
            "new_mode": new_mode,
            "calendar_context": cal_ctx,
        })

    def _format_user_patterns(self, trigger_type: str, trigger_value: str) -> str:
        """Build a text block describing matching user-defined patterns."""
        matches = pattern_agent.get_matching_patterns(trigger_type, trigger_value)
        if not matches:
            return "None"

        lines = []
        for p in matches:
            action_strs = [
                f"  - {a.device_id}.{a.action}({a.parameters})" for a in p.action_sequence
            ]
            lines.append(
                f"[{p.display_name}] (confidence={p.confidence})\n"
                f"  Description: {p.description}\n"
                f"  User said: \"{p.source_utterance}\"\n"
                f"  Actions:\n" + "\n".join(action_strs)
            )
        return "\n\n".join(lines)

    def _format_global_constraints(self) -> str:
        """Build a text block with ALL global constraint patterns + contextual ones.

        These are injected into EVERY LLM prompt so the model always respects
        user-defined rules like 'never unlock the door' or 'never turn off the fridge'.
        """
        constraints = pattern_agent.get_global_constraints()
        all_approved = pattern_agent.get_all_approved_patterns()

        if not all_approved:
            return ""

        lines = []

        # Global constraints first (highest priority)
        for p in constraints:
            lines.append(f"⚠ GLOBAL RULE: {p.description} (User said: \"{p.source_utterance}\")")

        # Also list contextual patterns as info (so LLM is aware)
        contextual = [p for p in all_approved if p.trigger_conditions.get("type") != "global"]
        if contextual:
            for p in contextual:
                trigger = p.trigger_conditions
                lines.append(
                    f"• Pattern [{p.display_name}]: {p.description} "
                    f"(trigger: {trigger.get('type')}={trigger.get('value')})"
                )

        return "\n".join(lines)

    # Regex that matches WHOLE-WORD prohibition keywords only.
    # Uses word-boundary \b to avoid matching "whenever" → "never", etc.
    _PROHIBITION_RE = re.compile(
        r"\b(never|don't|do not|prohibit|block|prevent|forbid)\b", re.IGNORECASE
    )

    def _is_prohibition_pattern(self, pattern) -> bool:
        """Return True only if a global pattern is a PROHIBITION (never do X).

        Positive automation patterns like 'Movie Mode: turn on TV' are NOT
        prohibitions and must not be blocked.
        Uses word-boundary matching to avoid false positives like 'whenever' → 'never'.
        """
        text = (
            (pattern.description or "") + " " + (pattern.source_utterance or "")
        )
        return bool(self._PROHIBITION_RE.search(text))

    def _get_blocked_actions_from_patterns(self) -> dict[str, set[str]]:
        """Extract device→blocked_actions map from global *prohibition* patterns.

        Only patterns whose description / source_utterance contains prohibition
        language ("never", "don't", …) are treated as blocks.  Positive global
        patterns (e.g. "when I say movie, turn on TV") are ignored here.

        Returns a dict like {"lock_front_door": {"unlock"}, "plug_kitchen_fridge": {"off"}}
        so that _execute_action_plan can enforce these at execution time.
        """
        blocked: dict[str, set[str]] = {}

        global_patterns = pattern_agent.get_global_constraints()
        logger.debug(
            f"Global constraint patterns: {len(global_patterns)} found"
        )
        for p in global_patterns:
            is_prohibition = self._is_prohibition_pattern(p)
            logger.debug(
                f"  Pattern '{p.display_name}': prohibition={is_prohibition}, "
                f"desc='{p.description[:60]}', src='{(p.source_utterance or '')[:60]}'"
            )
            if not is_prohibition:
                continue  # positive automation — skip
            for action in p.action_sequence:
                blocked.setdefault(action.device_id, set()).add(action.action)

        return blocked

    async def _execute_mode_transition(
        self, old_mode: str, new_mode: str, cal_ctx: dict[str, Any]
    ) -> None:
        """Use LLM to plan and execute device adjustments for a mode transition.

        Also looks up user-defined patterns that match the trigger and includes
        them in the LLM context so the model can honour user preferences.
        """
        device_inventory = self._build_device_inventory()

        # Look up user-defined patterns for this mode
        user_patterns_text = self._format_user_patterns("calendar_mode", new_mode)

        prompt = CALENDAR_RESPONSE_PROMPT.format(
            new_mode=new_mode,
            old_mode=old_mode,
            calendar_context=str(cal_ctx),
            user_location=user_info_agent.location.value,
            current_time=datetime.now().strftime("%H:%M"),
            device_inventory=device_inventory,
        )

        # Inject global constraints (always-on rules)
        global_constraints = self._format_global_constraints()
        if global_constraints:
            prompt += (
                "\n\n⚠ MANDATORY USER RULES (these override all other guidelines — "
                "violating these is FORBIDDEN):\n"
                f"{global_constraints}"
            )

        # Append trigger-specific user preferences as additional context
        if user_patterns_text != "None":
            prompt += (
                "\n\nCONTEXTUAL PREFERENCES (honour these for this mode):\n"
                "The user has explicitly taught these rules. Include ALL their "
                "requested actions in your plan IN ADDITION to the mode defaults.\n\n"
                f"{user_patterns_text}"
            )

        try:
            result = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            if "error" in result and "actions" not in result:
                logger.warning(f"LLM failed for mode transition: {result.get('error')}")
                await self._fallback_mode_transition(old_mode, new_mode)
                return

            reasoning = result.get("reasoning", "")
            actions = result.get("actions", [])
            voice_msg = result.get("voice_message", "")

            logger.info(f"LLM planned {len(actions)} mode-transition actions: {reasoning}")

            executed, failed = await self._execute_action_plan(actions)

            logger.info(
                f"Mode transition ({old_mode}→{new_mode}): "
                f"{len(executed)} executed, {len(failed)} failed"
            )
            if failed:
                logger.warning(f"Failed mode actions: {failed}")

            # Voice notification (respects DND: only text if suppressed)
            if voice_msg:
                await voice_agent.run(message=voice_msg, require_permission=False)

            await ws_manager.broadcast("orchestrator_action", {
                "type": "mode_transition",
                "old_mode": old_mode,
                "new_mode": new_mode,
                "reasoning": reasoning,
                "actions_executed": executed,
                "actions_failed": failed,
                "user_patterns_applied": user_patterns_text != "None",
            })

        except Exception as e:
            logger.error(f"LLM mode transition failed: {e}", exc_info=True)
            await self._fallback_mode_transition(old_mode, new_mode)

    async def _fallback_mode_transition(self, old_mode: str, new_mode: str) -> None:
        """Rule-based fallback for mode transitions when LLM is unavailable."""
        executed: list[str] = []
        pattern_blocked = self._get_blocked_actions_from_patterns()

        try:
            if new_mode == "preparing_for_meeting":
                # Office light on, dim other lights, lock door
                r = await home_state_agent.execute_action(
                    "light_office_main", "on", {"brightness": 80}
                )
                if r.get("success"):
                    executed.append("light_office_main.on(80)")

                for lid in ("light_living_main", "light_bedroom_main", "light_kitchen_main"):
                    r = await home_state_agent.execute_action(lid, "dim", {"brightness": 30})
                    if r.get("success"):
                        executed.append(f"{lid}.dim(30)")

                for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                    r = await home_state_agent.execute_action(device.device_id, "lock")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.lock")

                await voice_agent.run(
                    message="Your meeting starts soon. I've set up the office and dimmed other lights.",
                    require_permission=False,
                )

            elif new_mode in ("do_not_disturb", "focus"):
                # Office light stable, everything else off, eco mode
                r = await home_state_agent.execute_action(
                    "light_office_main", "on", {"brightness": 70}
                )
                if r.get("success"):
                    executed.append("light_office_main.on(70)")

                for device in device_registry.get_devices_by_type(DeviceType.LIGHT):
                    if device.device_id != "light_office_main" and device.state.power:
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    if "office" not in device.device_id:
                        r = await home_state_agent.execute_action(device.device_id, "eco_mode")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.eco_mode")

                for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                    r = await home_state_agent.execute_action(device.device_id, "lock")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.lock")

                for device in device_registry.get_devices_by_type(DeviceType.COFFEE_MAKER):
                    if device.state.power:
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

            elif new_mode == "sleep":
                # All lights off, lock doors, lower thermostat
                for device in device_registry.get_devices_by_type(DeviceType.LIGHT):
                    if device.state.power:
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                    r = await home_state_agent.execute_action(device.device_id, "lock")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.lock")

                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    await home_state_agent.execute_action(
                        device.device_id, "set_temperature", {"temperature": 68}
                    )
                    r = await home_state_agent.execute_action(
                        device.device_id, "set_mode", {"mode": "auto"}
                    )
                    if r.get("success"):
                        executed.append(f"{device.device_id}.auto(68)")

            elif new_mode == "active":
                # Bright lights in living room, comfortable temp
                r = await home_state_agent.execute_action(
                    "light_living_main", "on", {"brightness": 90}
                )
                if r.get("success"):
                    executed.append("light_living_main.on(90)")

                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    await home_state_agent.execute_action(
                        device.device_id, "set_temperature", {"temperature": 70}
                    )
                    r = await home_state_agent.execute_action(
                        device.device_id, "set_mode", {"mode": "auto"}
                    )
                    if r.get("success"):
                        executed.append(f"{device.device_id}.auto(70)")

            elif new_mode == "normal":
                # Restore from snapshot if available, otherwise set comfortable defaults
                if self._pre_mode_device_snapshot:
                    executed = await self._restore_from_snapshot()
                else:
                    # Comfortable defaults
                    default_lights = {
                        "light_living_main": 80,
                        "light_bedroom_main": 60,
                        "light_office_main": 50,
                        "light_kitchen_main": 80,
                    }
                    for lid, brightness in default_lights.items():
                        r = await home_state_agent.execute_action(
                            lid, "on", {"brightness": brightness}
                        )
                        if r.get("success"):
                            executed.append(f"{lid}.on({brightness})")

                    for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                        await home_state_agent.execute_action(
                            device.device_id, "set_temperature", {"temperature": 72}
                        )
                        r = await home_state_agent.execute_action(
                            device.device_id, "set_mode", {"mode": "auto"}
                        )
                        if r.get("success"):
                            executed.append(f"{device.device_id}.auto(72)")

                    # Unlock front door (user is home and meeting is over)
                    for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                        if user_info_agent.location.value == "home":
                            r = await home_state_agent.execute_action(device.device_id, "unlock")
                            if r.get("success"):
                                executed.append(f"{device.device_id}.unlock")

                await voice_agent.run(
                    message="Your meeting has ended. I've restored the house to normal.",
                    require_permission=False,
                )

        except Exception as e:
            logger.error(f"Fallback mode transition error: {e}", exc_info=True)

        logger.info(f"Fallback mode transition ({old_mode}→{new_mode}): {len(executed)} actions")

        await ws_manager.broadcast("orchestrator_action", {
            "type": "mode_transition_fallback",
            "old_mode": old_mode,
            "new_mode": new_mode,
            "actions_executed": executed,
        })

    async def _restore_from_snapshot(self) -> list[str]:
        """Restore device states from the pre-mode snapshot."""
        executed: list[str] = []
        snapshot = self._pre_mode_device_snapshot
        if not snapshot:
            return executed

        for device_id, saved in snapshot.items():
            device = device_registry.get_device(device_id)
            if not device:
                continue
            # Skip sensors, battery — we don't restore those
            if device.device_type in (DeviceType.SENSOR, DeviceType.BATTERY):
                continue

            current_state = device.state
            saved_power = saved.get("power", False)
            saved_props = saved.get("properties", {})

            try:
                if saved_power and not current_state.power:
                    # Was on, now off → turn on with saved properties
                    params = {}
                    if "brightness" in saved_props and device.device_type == DeviceType.LIGHT:
                        params["brightness"] = saved_props["brightness"]
                    r = await home_state_agent.execute_action(device_id, "on", params)
                    if r.get("success"):
                        executed.append(f"{device_id}.on({params})")

                elif not saved_power and current_state.power:
                    # Was off, now on → turn off
                    r = await home_state_agent.execute_action(device_id, "off")
                    if r.get("success"):
                        executed.append(f"{device_id}.off")

                # Restore thermostat settings
                if device.device_type == DeviceType.THERMOSTAT:
                    if "target_temperature" in saved_props:
                        await home_state_agent.execute_action(
                            device_id,
                            "set_temperature",
                            {"temperature": saved_props["target_temperature"]},
                        )
                    if "mode" in saved_props:
                        r = await home_state_agent.execute_action(
                            device_id,
                            "set_mode",
                            {"mode": saved_props["mode"]},
                        )
                        if r.get("success"):
                            executed.append(f"{device_id}.set_mode({saved_props['mode']})")

                # Restore lock state
                if device.device_type == DeviceType.LOCK:
                    is_locked = saved_props.get("locked", False)
                    action = "lock" if is_locked else "unlock"
                    r = await home_state_agent.execute_action(device_id, action)
                    if r.get("success"):
                        executed.append(f"{device_id}.{action}")

            except Exception as e:
                logger.warning(f"Snapshot restore failed for {device_id}: {e}")

        logger.info(f"Restored {len(executed)} devices from snapshot")
        return executed

    # ------------------------------------------------------------------
    # Location handling
    # ------------------------------------------------------------------

    async def handle_location_change(self, new_location: str) -> None:
        """Handle a GPS location change by dynamically adjusting devices using LLM."""
        # Dedup: don't repeat for the same location
        if self._last_location_handled == new_location:
            return
        self._last_location_handled = new_location

        logger.info(f"Handling location change: {new_location}")

        device_inventory = self._build_device_inventory()

        # Look up user-defined patterns for this location
        user_patterns_text = self._format_user_patterns("location", new_location)

        prompt = LOCATION_RESPONSE_PROMPT.format(
            current_location=new_location,
            device_inventory=device_inventory,
        )

        # Inject global constraints (always-on rules)
        global_constraints = self._format_global_constraints()
        if global_constraints:
            prompt += (
                "\n\n⚠ MANDATORY USER RULES (these override all other guidelines — "
                "violating these is FORBIDDEN):\n"
                f"{global_constraints}"
            )

        if user_patterns_text != "None":
            prompt += (
                "\n\nCONTEXTUAL PREFERENCES (honour these for this trigger):\n"
                f"{user_patterns_text}"
            )

        try:
            result = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            if "error" in result and "actions" not in result:
                logger.warning(f"LLM failed for location response: {result.get('error')}")
                await self._fallback_location_response(new_location)
                return

            reasoning = result.get("reasoning", "")
            actions = result.get("actions", [])

            logger.info(f"LLM planned {len(actions)} location actions: {reasoning}")

            executed, failed = await self._execute_action_plan(actions)

            # Voice notification
            if new_location in ("away", "leaving"):
                await voice_agent.run(
                    message=(
                        f"You appear to be {new_location}. "
                        "I've secured the home and turned off non-essential devices."
                    ),
                    require_permission=False,
                )
            elif new_location == "arriving":
                await voice_agent.run(
                    message=(
                        "Welcome home! I've turned on the lights "
                        "and adjusted the temperature for you."
                    ),
                    require_permission=False,
                )

            self._decision_history.append({
                "threat_key": f"location_{new_location}",
                "assessment": f"Location: {new_location}",
                "actions_executed": True,
                "timestamp": datetime.now().isoformat(),
            })

            await ws_manager.broadcast("orchestrator_action", {
                "type": "location_response",
                "location": new_location,
                "reasoning": reasoning,
                "actions_executed": executed,
                "actions_failed": failed,
            })

        except Exception as e:
            logger.error(f"Location response failed: {e}", exc_info=True)
            await self._fallback_location_response(new_location)

    def _is_action_blocked(self, device_id: str, action_name: str, pattern_blocked: dict[str, set[str]]) -> bool:
        """Check if an action is blocked by hardcoded protections or user constraints."""
        if device_id in self._PROTECTED_DEVICE_IDS and action_name == "off":
            return True
        if device_id in pattern_blocked and action_name in pattern_blocked[device_id]:
            return True
        return False

    async def _fallback_location_response(self, location: str) -> None:
        """Rule-based fallback for location changes when LLM is unavailable."""
        executed: list[str] = []
        pattern_blocked = self._get_blocked_actions_from_patterns()

        try:
            if location in ("away", "leaving"):
                # Lock doors
                for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                    if self._is_action_blocked(device.device_id, "lock", pattern_blocked):
                        logger.info(f"Skipping {device.device_id}.lock (blocked by constraint)")
                        continue
                    r = await home_state_agent.execute_action(device.device_id, "lock")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.lock")

                # Turn off ALL lights
                for device in device_registry.get_devices_by_type(DeviceType.LIGHT):
                    if device.state.power:
                        if self._is_action_blocked(device.device_id, "off", pattern_blocked):
                            logger.info(f"Skipping {device.device_id}.off (blocked by constraint)")
                            continue
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                # Turn off non-critical smart plugs
                for device in device_registry.get_devices_by_type(DeviceType.SMART_PLUG):
                    if (
                        device.state.priority_tier != PriorityTier.CRITICAL
                        and device.state.power
                    ):
                        if self._is_action_blocked(device.device_id, "off", pattern_blocked):
                            logger.info(f"Skipping {device.device_id}.off (blocked by constraint)")
                            continue
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                # Turn off coffee maker
                for device in device_registry.get_devices_by_type(DeviceType.COFFEE_MAKER):
                    if device.state.power:
                        if self._is_action_blocked(device.device_id, "off", pattern_blocked):
                            logger.info(f"Skipping {device.device_id}.off (blocked by constraint)")
                            continue
                        r = await home_state_agent.execute_action(device.device_id, "off")
                        if r.get("success"):
                            executed.append(f"{device.device_id}.off")

                # Eco mode on thermostats
                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    if self._is_action_blocked(device.device_id, "eco_mode", pattern_blocked):
                        logger.info(f"Skipping {device.device_id}.eco_mode (blocked by constraint)")
                        continue
                    r = await home_state_agent.execute_action(device.device_id, "eco_mode")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.eco_mode")

            elif location == "arriving":
                # Unlock front door
                for device in device_registry.get_devices_by_type(DeviceType.LOCK):
                    if self._is_action_blocked(device.device_id, "unlock", pattern_blocked):
                        logger.info(f"Skipping {device.device_id}.unlock (blocked by constraint)")
                        continue
                    r = await home_state_agent.execute_action(device.device_id, "unlock")
                    if r.get("success"):
                        executed.append(f"{device.device_id}.unlock")

                # Turn on main lights
                for device_id in ["light_living_main", "light_kitchen_main"]:
                    r = await home_state_agent.execute_action(
                        device_id, "on", {"brightness": 80}
                    )
                    if r.get("success"):
                        executed.append(f"{device_id}.on(80)")

                # Restore thermostat to comfortable
                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    await home_state_agent.execute_action(
                        device.device_id, "set_temperature", {"temperature": 72}
                    )
                    r = await home_state_agent.execute_action(
                        device.device_id, "set_mode", {"mode": "auto"}
                    )
                    if r.get("success"):
                        executed.append(f"{device.device_id}.auto(72)")

            elif location == "home":
                # Ensure comfortable settings
                for device in device_registry.get_devices_by_type(DeviceType.THERMOSTAT):
                    await home_state_agent.execute_action(
                        device.device_id, "set_temperature", {"temperature": 72}
                    )
                    r = await home_state_agent.execute_action(
                        device.device_id, "set_mode", {"mode": "auto"}
                    )
                    if r.get("success"):
                        executed.append(f"{device.device_id}.auto(72)")

        except Exception as e:
            logger.error(f"Fallback location response error: {e}", exc_info=True)

        logger.info(f"Fallback location response ({location}): {len(executed)} actions")

        # Voice notification for fallback too
        if location in ("away", "leaving"):
            await voice_agent.run(
                message=(
                    f"You appear to be {location}. "
                    "I've secured the home and adjusted devices to save energy."
                ),
                require_permission=False,
            )
        elif location == "arriving":
            await voice_agent.run(
                message="Welcome home! Lights and temperature are set for you.",
                require_permission=False,
            )

        self._decision_history.append({
            "threat_key": f"location_{location}",
            "assessment": f"Location: {location} (fallback)",
            "actions_executed": True,
            "timestamp": datetime.now().isoformat(),
        })

        await ws_manager.broadcast("orchestrator_action", {
            "type": "location_response_fallback",
            "location": location,
            "actions_executed": executed,
        })

    # ------------------------------------------------------------------
    # Clarity check for voice-transcribed commands
    # ------------------------------------------------------------------

    CLARITY_PROMPT = (
        "You are checking whether a speech-to-text transcription is understandable English.\n"
        "Your ONLY job is to detect GIBBERISH — random letters, nonsensical syllables, or garbled noise. \n\n"
        'TRANSCRIPTION: "{text}"\n\n'
        "Respond with ONLY valid JSON:\n"
        '{{"is_clear": true, "cleaned_text": "the text with minor STT fixes"}}\n'
        "or\n"
        '{{"is_clear": false, "reason": "why it is gibberish"}}\n\n'
        "Rules:\n"
        "- If the text is understandable English (even if informal, a statement, a question, or a feeling), return is_clear=true.\n"
        "- 'I feel cold' → CLEAR. 'Turn off the lights' → CLEAR. 'What is the temperature?' → CLEAR.\n"
        "- 'it is hot today' → CLEAR. 'good morning' → CLEAR. 'lock everything' → CLEAR.\n"
        "- ONLY return is_clear=false for actual gibberish: random letters, broken syllables, or completely unintelligible text.\n"
        "- 'asdfjkl' → NOT CLEAR. \n"
        "If you can find proper statements in the speech the text is clear."
        "- When in doubt, return is_clear=true. You must be very permissive."
    )

    async def check_command_clarity(self, text: str) -> dict[str, Any]:
        """Check if a voice-transcribed command is clear enough to act on.

        Returns:
            dict with 'is_clear' (bool), optionally 'cleaned_text' or 'message'
        """
        try:
            result = await llm_client.chat_json(
                messages=[{
                    "role": "user",
                    "content": self.CLARITY_PROMPT.format(text=text),
                }],
                temperature=0.0,
                max_tokens=150,
            )

            is_clear = result.get("is_clear", True)
            if is_clear:
                return {
                    "is_clear": True,
                    "cleaned_text": result.get("cleaned_text", text),
                }
            else:
                reason = result.get("reason", "unclear input")
                return {
                    "is_clear": False,
                    "message": f"I didn't quite understand that ({reason}). Could you try again or type your request?",
                }

        except Exception as e:
            logger.warning(f"Clarity check failed, allowing command through: {e}")
            # If LLM fails, let the command through rather than blocking
            return {"is_clear": True, "cleaned_text": text}

    # ------------------------------------------------------------------
    # Intent classification for user messages
    # ------------------------------------------------------------------

    INTENT_PROMPT = (
        "Classify the following user message into EXACTLY ONE of these intents:\n"
        '- "command": The user wants to execute an action or express a state RIGHT NOW.\n'
        '- "preference": The user is explicitly teaching a RULE for the FUTURE.\n'
        '- "both": The user wants to execute now AND also save a rule for the future.\n'
        "\n"
        "CRITICAL RULES:\n"
        "1. Default to 'command'. Almost everything is a command.\n"
        "2. A message is ONLY a 'preference' if it contains EXPLICIT conditional/teaching language like:\n"
        '   "when", "whenever", "always", "never", "remember to", "from now on", "if ... then", "every time", "during", "don\'t ever"\n'
        "3. Statements about how the user feels, descriptions of conditions, or requests for action are ALWAYS 'command':\n"
        '   "I feel cold" → command.  "It is hot" → command.  "Make it warmer" → command.\n'
        '   "Turn off all lights" → command.  "What is the temperature?" → command.\n'
        "4. 'both' is VERY rare — only when the user explicitly says to do something now AND save it.\n"
        "\n"
        'USER MESSAGE: "{message}"\n'
        "\n"
        "Respond with ONLY valid JSON:\n"
        '{{"intent": "command|preference|both", "reasoning": "one line explanation"}}'
    )

    async def _classify_intent(self, message: str) -> str:
        """Classify a user message as command, preference, or both."""
        try:
            result = await llm_client.chat_json(
                messages=[{
                    "role": "user",
                    "content": self.INTENT_PROMPT.format(message=message),
                }],
                temperature=0.0,
                max_tokens=100,
            )
            intent = result.get("intent", "command").lower().strip()
            if intent not in ("command", "preference", "both"):
                intent = "command"
            logger.info(f"Intent classified as '{intent}': {result.get('reasoning', '')}")
            return intent
        except Exception as e:
            logger.warning(f"Intent classification failed, defaulting to command: {e}")
            return "command"

    # ------------------------------------------------------------------
    # General command processing (user-initiated)
    # ------------------------------------------------------------------

    async def run(self, request: str, source: str = "text", **kwargs) -> dict[str, Any]:
        """Process a natural language command or agent request.

        Args:
            request: The user's natural language command.
            source: "text" or "voice". When "voice", always provides audio feedback.
        """
        self._status = AgentStatus.RUNNING

        try:
            device_inventory = self._build_device_inventory()

            context = {
                "threat_summary": threat_agent.latest_assessment.summary or "No threats",
                "user_location": user_info_agent.location.value,
                "calendar_context": str(user_info_agent.calendar_context),
                "energy_summary": str(home_state_agent.get_energy_summary()),
                "device_inventory": device_inventory,
                "patterns": str([
                    {
                        "name": p.display_name,
                        "type": p.pattern_type.value,
                        "description": p.description,
                        "approved": p.approved,
                        "trigger": p.trigger_conditions,
                    }
                    for p in pattern_agent.patterns.values()
                    if p.approved
                ][:10]),
            }

            prompt = ORCHESTRATOR_PROMPT.format(request=request, **context)

            # Inject global constraints
            global_constraints = self._format_global_constraints()
            if global_constraints:
                prompt += (
                    "\n\n⚠ MANDATORY USER RULES (these override all other guidelines — "
                    "violating these is FORBIDDEN):\n"
                    f"{global_constraints}"
                )

            result = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            if "error" in result and "raw" not in result:
                # Even on error, provide voice feedback if source is voice
                if source == "voice":
                    await voice_agent.run(
                        message="Sorry, I had trouble processing that request. Could you try again?",
                        require_permission=False,
                    )
                return {"success": False, "error": result["error"]}

            reasoning = result.get("reasoning", "")
            actions = result.get("actions", [])
            alert_msg = result.get("alert_message", "")
            require_perm = result.get("require_permission", False)
            not_understood = result.get("not_understood", False)

            # If the LLM says it doesn't understand, or there are zero actions
            # and no alert message, treat it as "not understood"
            if not_understood or (not actions and not alert_msg):
                logger.info(f"Request not understood or no actions: '{request}'")
                no_action_msg = (
                    "I'm not sure what you'd like me to do with the home. "
                    "Could you rephrase that, or try something like "
                    "'turn on the lights' or 'set the temperature to 72'?"
                )
                if source == "voice":
                    await voice_agent.run(message=no_action_msg, require_permission=False)

                self._status = AgentStatus.IDLE
                return {
                    "success": False,
                    "unclear": True,
                    "message": no_action_msg,
                    "reasoning": reasoning,
                    "actions_executed": 0,
                }

            # Execute actions via shared helper
            executed, failed = await self._execute_action_plan(actions)

            # Log for pattern detection
            for action in actions:
                device_id = action.get("device_id", "")
                act = action.get("action", "")
                params = action.get("parameters", {})
                if device_id:
                    await pattern_agent.log_device_event(
                        device_id=device_id,
                        action=act,
                        params=params,
                        source="orchestrator",
                    )

            # Voice feedback
            voice_sent = False
            if alert_msg:
                await voice_agent.run(message=alert_msg, require_permission=require_perm)
                voice_sent = True

            # For voice commands, always provide audio feedback
            if source == "voice" and not voice_sent:
                feedback = reasoning if reasoning else "Done, I've processed your request."
                await voice_agent.run(message=feedback, require_permission=False)

            # Log decision
            decision = {
                "request": request,
                "reasoning": reasoning,
                "actions_count": len(actions),
                "timestamp": datetime.now().isoformat(),
            }
            self._decision_history.append(decision)

            await event_store.log_event(Event(
                event_id=str(uuid.uuid4())[:8],
                event_type=EventType.AGENT_DECISION,
                source=self.agent_id,
                data={"request": request, "reasoning": reasoning, "actions": len(actions)},
            ))

            self._record_action(
                action=f"Command: {request[:80]}",
                reasoning=reasoning[:500],
            )

            await ws_manager.broadcast("orchestrator_action", {
                "request": request,
                "reasoning": reasoning,
                "actions_executed": executed,
                "actions_failed": failed,
            })

            self._status = AgentStatus.IDLE
            return {
                "success": True,
                "reasoning": reasoning,
                "actions_executed": len(executed),
                "actions_failed": len(failed),
                "results": executed,
            }

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            self._status = AgentStatus.ERROR
            self._error = str(e)
            return {"success": False, "error": str(e)}

    async def handle_user_command(self, command: str, source: str = "text") -> dict[str, Any]:
        """Handle a natural language command from the user.

        Args:
            command: The user's natural language command.
            source: "text" or "voice". When "voice", audio feedback is always produced.

        First classifies the intent:
        - command  → execute actions now (existing flow)
        - preference → save as a pattern for future automation
        - both → execute now AND save as a pattern
        """
        logger.info(f"User command ({source}): {command}")
        await pattern_agent.log_device_event(
            device_id="user",
            action="command",
            params={"text": command},
            source="user",
        )

        # Step 1: Classify intent
        intent = await self._classify_intent(command)

        result: dict[str, Any] = {"success": True}

        # Step 2: If preference or both, learn the pattern
        if intent in ("preference", "both"):
            device_inventory = self._build_device_inventory()
            learn_result = await pattern_agent.learn_user_preference(
                user_message=command,
                device_inventory=device_inventory,
            )
            result["pattern_learned"] = learn_result

            if intent == "preference":
                # Pure preference — don't execute, just confirm learning
                if learn_result.get("success"):
                    confirm_msg = (
                        f"Got it! I've learned the pattern: "
                        f"{learn_result.get('description', command)}. "
                        f"I'll remember this for next time."
                    )
                    # Always provide voice feedback for preferences (both text and voice)
                    await voice_agent.run(message=confirm_msg, require_permission=False)
                    result["reasoning"] = "Saved as a preference for future use"
                    result["actions_executed"] = 0

                    await ws_manager.broadcast("orchestrator_action", {
                        "request": command,
                        "reasoning": "Saved as user preference",
                        "pattern_learned": learn_result,
                    })
                else:
                    # Fallback: if preference parsing failed, execute as command
                    logger.warning("Preference parsing failed, executing as command")
                    result = await self.run(command, source=source)
                return result

        # Step 3: Execute as command (for "command" or "both")
        exec_result = await self.run(command, source=source)
        result.update(exec_result)

        # If both, inform about the learned pattern too
        if intent == "both" and result.get("pattern_learned", {}).get("success"):
            learned = result["pattern_learned"]
            await voice_agent.run(
                message=(
                    f"Done! I've also saved this as a pattern: "
                    f"{learned.get('description', '')}. "
                    f"I'll do this automatically next time."
                ),
                require_permission=False,
            )

        return result

    def get_all_agent_info(self) -> list[dict[str, Any]]:
        """Get status info for all agents."""
        return [
            self.info,
            home_state_agent.info,
            threat_agent.info,
            voice_agent.info,
            pattern_agent.info,
            user_info_agent.info,
        ]


# Singleton
orchestrator = OrchestratorAgent()
