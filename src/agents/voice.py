"""Voice Call Agent -- generates voice alerts via ElevenLabs and manages user permissions."""

import asyncio
import base64
import logging
import uuid
from typing import Any

from src.agents.base import BaseAgent, AgentStatus
from src.integrations.elevenlabs import tts_client
from src.integrations.openrouter import llm_client
from src.storage.event_store import event_store
from src.models.events import Event, EventType
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)

def _build_action_descriptions() -> dict[str, str]:
    """Build a human-readable action descriptions map dynamically.

    Combines device-level actions from the schema with higher-level
    threat-response action phrases.  The device-level entries are
    auto-generated so they stay in sync with DEVICE_TYPE_ACTIONS.
    """
    from src.models.device import DEVICE_TYPE_ACTIONS

    descs: dict[str, str] = {}

    # Auto-generated device-level descriptions
    _FRIENDLY: dict[str, dict[str, str]] = {
        "light": {"on": "turn on the lights", "off": "turn off the lights", "dim": "dim the lights"},
        "thermostat": {
            "set_temperature": "adjust the thermostat temperature",
            "set_mode": "change the thermostat mode",
            "eco_mode": "switch the thermostat to eco mode",
        },
        "smart_plug": {"on": "turn on the smart plug", "off": "turn off the smart plug"},
        "lock": {"lock": "lock the door", "unlock": "unlock the door"},
        "coffee_maker": {"brew": "brew coffee", "off": "turn off the coffee maker", "on": "switch on the coffee maker", "keep_warm": "keep the coffee warm"},
        "battery": {"set_mode": "adjust the home battery mode"},
        "water_heater": {"heat": "heat the water", "boost": "boost the water heater", "standby": "set the water heater to standby", "off": "turn off the water heater"},
    }

    for type_key, actions in DEVICE_TYPE_ACTIONS.items():
        # DEVICE_TYPE_ACTIONS is dict[str, list[dict[str, Any]]]
        # type_key is already a string (e.g., "light", "thermostat")
        # actions is a list of dicts with "action" and "params" keys
        for action_dict in actions:
            action_name = action_dict["action"]  # Extract action name from dict
            key = f"{type_key}_{action_name}"
            friendly = _FRIENDLY.get(type_key, {}).get(action_name, f"{action_name} the {type_key}".replace("_", " "))
            descs[key] = friendly
            descs[action_name] = friendly  # also allow bare action name

    # Higher-level threat-response phrases (not tied to a single device)
    descs.update({
        "pre_cool_home": "pre-cool the house before the heat peaks",
        "pre_cool": "pre-cool the house before the heat peaks",
        "charge_battery": "charge the home battery to prepare for high demand",
        "switch_to_battery": "switch to battery backup power",
        "close_blinds": "close the blinds and dim the lights to reduce solar heat gain",
        "reduce_non_essential": "turn off non-essential devices to conserve energy",
        "reduce_consumption": "reduce overall energy consumption",
        "set_eco_mode": "switch thermostats to energy-saving eco mode",
        "increase_heating": "increase heating to keep the house warm and protect the pipes",
        "defer_high_energy_tasks": "delay any high-energy tasks until prices drop",
        "insulate_pipes_alert": "check that exposed pipes are insulated against freezing",
    })

    return descs


# Lazy-initialised once at first use
_ACTION_DESCRIPTIONS: dict[str, str] | None = None


def _get_action_descriptions() -> dict[str, str]:
    global _ACTION_DESCRIPTIONS
    if _ACTION_DESCRIPTIONS is None:
        _ACTION_DESCRIPTIONS = _build_action_descriptions()
    return _ACTION_DESCRIPTIONS

SCRIPT_GENERATION_PROMPT = """You are a friendly smart home assistant speaking to the homeowner.
Convert the following technical threat information into a natural, conversational voice message.

RULES:
- Speak naturally as if you're a helpful assistant, not a robot
- Keep it concise (2-4 sentences max)
- Don't use technical jargon, function names, or underscores
- Be warm but direct about urgency
- If permission is needed, end with a clear yes/no question

THREAT INFO:
- Summary: {summary}
- Threat Level: {threat_level}
- Actions I want to take: {actions_human_readable}
- Permission needed: {needs_permission}

Generate ONLY the voice script text, no JSON or formatting."""


class VoiceAgent(BaseAgent):
    """Voice Call Agent: TTS alerts and user permission management."""

    def __init__(self):
        super().__init__("voice_agent", "Voice Call Agent")
        self._pending_permissions: dict[str, asyncio.Future] = {}
        self._alert_history: list[dict[str, Any]] = []
        self._dnd_active: bool = False
        self._dnd_reason: str = ""

    # ------------------------------------------------------------------
    # Do-Not-Disturb mode management
    # ------------------------------------------------------------------

    @property
    def dnd_active(self) -> bool:
        return self._dnd_active

    def set_dnd_mode(self, active: bool, reason: str = "") -> None:
        """Enable or disable Do-Not-Disturb mode.

        When DND is active, only critical/high-priority alerts (those that require
        permission or have threat_level in [high, critical]) will produce TTS audio.
        Lower-priority alerts are silently logged and broadcast as text-only.
        """
        was_active = self._dnd_active
        self._dnd_active = active
        self._dnd_reason = reason
        if active and not was_active:
            logger.info(f"Voice DND enabled: {reason}")
        elif not active and was_active:
            logger.info("Voice DND disabled — normal alert mode restored")

    async def generate_script(
        self,
        summary: str,
        threat_level: str,
        actions: list[str],
        needs_permission: bool,
    ) -> str:
        """Use LLM to generate a natural, conversational voice script.

        Falls back to a template-based approach if LLM fails.
        """
        # Convert technical action names to human-readable (dynamic lookup)
        descriptions = _get_action_descriptions()
        actions_readable = []
        for action in actions:
            action_lower = action.lower().replace(" ", "_")
            desc = descriptions.get(action_lower)
            if not desc:
                # Try partial match
                for key, val in descriptions.items():
                    if key in action_lower or action_lower in key:
                        desc = val
                        break
            actions_readable.append(desc or action.replace("_", " "))

        try:
            prompt = SCRIPT_GENERATION_PROMPT.format(
                summary=summary,
                threat_level=threat_level,
                actions_human_readable=", ".join(actions_readable),
                needs_permission="yes — ask for approval" if needs_permission else "no — just inform",
            )

            script = await llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=300,
            )

            # Strip any quotes or extra formatting
            script = script.strip().strip('"').strip("'")
            if script and "error" not in script.lower()[:20]:
                return script

        except Exception as e:
            logger.warning(f"Script generation failed, using fallback: {e}")

        # Fallback: template-based natural script
        return self._fallback_script(summary, actions_readable, needs_permission)

    def _fallback_script(
        self, summary: str, actions_readable: list[str], needs_permission: bool
    ) -> str:
        """Generate a natural-sounding fallback script without LLM."""
        script = f"Hey, I wanted to let you know — {summary.lower()}. "

        if actions_readable:
            if len(actions_readable) == 1:
                script += f"I'd like to {actions_readable[0]}. "
            elif len(actions_readable) == 2:
                script += f"I'd like to {actions_readable[0]} and {actions_readable[1]}. "
            else:
                items = ", ".join(actions_readable[:-1])
                script += f"I'd like to {items}, and {actions_readable[-1]}. "

        if needs_permission:
            script += "Should I go ahead with that?"
        else:
            script += "I'm taking care of it now."

        return script

    async def run(
        self,
        message: str,
        require_permission: bool = False,
        alert_id: str | None = None,
        threat_summary: str = "",
        threat_level: str = "",
        actions: list[str] | None = None,
    ) -> dict[str, Any]:
        """Generate a voice alert and optionally wait for user permission.

        Args:
            message: The alert text to speak (used as-is if no threat context given)
            require_permission: Whether to wait for user approval
            alert_id: Unique ID for this alert (auto-generated if not provided)
            threat_summary: Summary for script generation
            threat_level: Level for script generation
            actions: Technical action names for script generation

        Returns:
            dict with 'audio_base64' (if TTS succeeded), 'approved' (if permission required)
        """
        self._status = AgentStatus.RUNNING
        aid = alert_id or str(uuid.uuid4())[:8]

        # If threat context is provided, generate a natural script
        if threat_summary and actions:
            message = await self.generate_script(
                summary=threat_summary,
                threat_level=threat_level,
                actions=actions,
                needs_permission=require_permission,
            )

        # ---- DND suppression logic ----
        # If DND is active, only allow critical alerts through with audio.
        # Non-critical alerts are still logged and broadcast as text, just no TTS.
        is_critical = require_permission or threat_level in ("high", "critical")
        suppress_audio = self._dnd_active and not is_critical

        if suppress_audio:
            logger.info(f"DND active — suppressing TTS for: {message[:80]}")

        try:
            # Generate TTS audio (skip if DND-suppressed)
            audio_bytes = None
            if not suppress_audio:
                audio_bytes = await tts_client.text_to_speech(message)
            audio_b64 = base64.b64encode(audio_bytes).decode() if audio_bytes else None

            alert = {
                "alert_id": aid,
                "message": message,
                "audio_base64": audio_b64,
                "require_permission": require_permission,
                "status": "pending" if require_permission else "info",
                "dnd_suppressed": suppress_audio,
            }
            self._alert_history.append(alert)

            # Broadcast to frontend
            await ws_manager.broadcast("voice_alert", alert)

            # Log event
            await event_store.log_event(Event(
                event_id=aid,
                event_type=EventType.VOICE_ALERT,
                source=self.agent_id,
                data={"message": message, "require_permission": require_permission},
            ))

            self._record_action(
                action=f"Voice alert: {message[:80]}",
                reasoning=f"Permission required: {require_permission}",
            )

            if require_permission:
                # Create a future to wait for user response
                future: asyncio.Future = asyncio.get_event_loop().create_future()
                self._pending_permissions[aid] = future

                try:
                    # Wait up to 60 seconds for user response
                    result = await asyncio.wait_for(future, timeout=60.0)
                    del self._pending_permissions[aid]
                    return {
                        "alert_id": aid,
                        "audio_base64": audio_b64,
                        "approved": result.get("approved", False),
                        "user_response": result,
                    }
                except asyncio.TimeoutError:
                    del self._pending_permissions[aid]
                    logger.warning(f"Permission timeout for alert {aid}")
                    await ws_manager.broadcast("voice_alert_timeout", {"alert_id": aid})
                    return {
                        "alert_id": aid,
                        "audio_base64": audio_b64,
                        "approved": False,
                        "timeout": True,
                    }

            self._status = AgentStatus.IDLE
            return {"alert_id": aid, "audio_base64": audio_b64, "approved": True}

        except Exception as e:
            logger.error(f"Voice agent error: {e}")
            self._status = AgentStatus.ERROR
            self._error = str(e)
            return {"alert_id": aid, "error": str(e), "approved": False}

    async def handle_permission_response(self, alert_id: str, approved: bool, modifications: dict = {}) -> bool:
        """Handle user's permission response from the frontend.

        Args:
            alert_id: The alert ID to respond to
            approved: Whether the user approved the action
            modifications: Any modifications the user requested

        Returns:
            True if the response was processed successfully
        """
        future = self._pending_permissions.get(alert_id)
        if not future:
            logger.warning(f"No pending permission for alert {alert_id}")
            return False

        future.set_result({
            "approved": approved,
            "modifications": modifications,
        })

        # Broadcast response
        await ws_manager.broadcast("voice_alert_response", {
            "alert_id": alert_id,
            "approved": approved,
            "modifications": modifications,
        })

        await event_store.log_event(Event(
            event_id=str(uuid.uuid4())[:8],
            event_type=EventType.USER_ACTION,
            source="user",
            data={
                "alert_id": alert_id,
                "approved": approved,
                "modifications": modifications,
            },
        ))

        return True

    @property
    def alert_history(self) -> list[dict[str, Any]]:
        return self._alert_history[-50:]  # Last 50 alerts

    @property
    def pending_count(self) -> int:
        return len(self._pending_permissions)


# Singleton
voice_agent = VoiceAgent()
