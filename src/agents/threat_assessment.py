"""Threat Assessment Agent (The Oracle) -- data fusion and threat detection."""

import asyncio
import logging
import uuid
from typing import Any

from config import settings
from src.agents.base import BaseAgent, AgentStatus
from src.integrations.openweather import weather_client
from src.integrations.ercot import ercot_client
from src.integrations.openrouter import llm_client
from src.models.threat import ThreatAssessment, ThreatLevel, ThreatType, WeatherData, ERCOTData
from src.storage.event_store import event_store
from src.models.events import Event, EventType
from src.mqtt.client import mqtt_client
from src.mqtt.topics import Topics
from src.api.websocket import ws_manager

logger = logging.getLogger(__name__)

THREAT_ANALYSIS_PROMPT = """You are a threat assessment AI for a smart home in Texas (ERCOT grid).
Analyze the following weather and grid data to identify the SINGLE most urgent threat.

WEATHER DATA:
- Temperature: {temp_f}°F (feels like {feels_like_f}°F)
- Humidity: {humidity}%
- Wind: {wind_mph} mph
- Conditions: {description}
- Forecast High: {forecast_high}°F
- Forecast Low: {forecast_low}°F
- Weather Alerts: {alerts}

ERCOT GRID DATA:
- System Load: {load_mw} MW
- Load Capacity: {load_pct}%
- LMP Price: ${lmp}/MWh
- Operating Reserves: {reserves_mw} MW
- Grid Alert Level: {grid_alert}

Respond with ONLY valid JSON. Choose exactly ONE value for each enum field:

threat_level must be exactly one of: "none", "low", "medium", "high", "critical"
threat_type must be exactly one of: "none", "heat_wave", "grid_strain", "power_outage", "storm", "cold_snap"

For recommended_actions, use these exact action names:
- "pre_cool_home" (lower thermostat to cool before peak heat)
- "increase_heating" (raise thermostat during cold)
- "set_eco_mode" (energy-saving thermostat mode)
- "charge_battery" (charge home battery)
- "switch_to_battery" (use battery backup)
- "close_blinds" (close blinds / dim lights to reduce solar heat)
- "reduce_non_essential" (turn off non-essential devices)
- "defer_high_energy_tasks" (postpone high-energy activities)

{{
    "threat_level": "high",
    "threat_type": "heat_wave",
    "urgency_score": 0.8,
    "summary": "Brief one-line summary of the threat",
    "reasoning": "Detailed reasoning for this assessment",
    "recommended_actions": ["pre_cool_home", "charge_battery"]
}}

Threat thresholds:
- Temps > 100°F = heat_wave
- Temps < 32°F = cold_snap
- Grid load > 85% = grid_strain
- Grid load > 95% = power_outage risk
- LMP > $100/MWh = high energy costs
- Reserves < 2000 MW = emergency
- Severe weather = storm"""


class ThreatAssessmentAgent(BaseAgent):
    """The Oracle: fuses weather + grid data into threat assessments."""

    def __init__(self):
        super().__init__("threat_oracle", "Threat Assessment Agent (The Oracle)")
        self._latest_assessment: ThreatAssessment = ThreatAssessment()
        self._poll_task: asyncio.Task | None = None
        self._weather_data: WeatherData = WeatherData()
        self._ercot_data: ERCOTData = ERCOTData()

    @property
    def latest_assessment(self) -> ThreatAssessment:
        return self._latest_assessment

    @property
    def weather_data(self) -> WeatherData:
        return self._weather_data

    @property
    def ercot_data(self) -> ERCOTData:
        return self._ercot_data

    async def start(self) -> None:
        await super().start()
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
        """Continuously poll weather and grid data."""
        try:
            while True:
                await self.run()
                # Poll every 2 minutes (grid) -- weather is cached by OpenWeatherMap
                await asyncio.sleep(settings.ercot_poll_interval_seconds)
        except asyncio.CancelledError:
            pass

    async def run(self, *args, **kwargs) -> ThreatAssessment:
        """Fetch data and produce threat assessment."""
        self._status = AgentStatus.RUNNING

        try:
            # Fetch both data sources in parallel
            self._weather_data, self._ercot_data = await asyncio.gather(
                weather_client.get_forecast(),
                ercot_client.get_grid_conditions(),
            )

            # Synthesize threat assessment using LLM
            assessment = await self._analyze_threats(self._weather_data, self._ercot_data)
            self._latest_assessment = assessment

            # Helper to safely get string value from enum or string
            def _get_enum_str(val):
                return val.value if hasattr(val, 'value') else str(val)

            threat_level_str = _get_enum_str(assessment.threat_level)
            threat_type_str = _get_enum_str(assessment.threat_type)

            # Log event
            await event_store.log_event(Event(
                event_id=str(uuid.uuid4())[:8],
                event_type=EventType.THREAT_ASSESSMENT,
                source=self.agent_id,
                data={
                    "threat_level": threat_level_str,
                    "threat_type": threat_type_str,
                    "summary": assessment.summary,
                    "urgency_score": assessment.urgency_score,
                },
            ))

            # Publish to MQTT
            await mqtt_client.publish(Topics.THREAT_ASSESSMENT, {
                "threat_level": threat_level_str,
                "threat_type": threat_type_str,
                "urgency_score": assessment.urgency_score,
                "summary": assessment.summary,
                "reasoning": assessment.reasoning,
                "recommended_actions": assessment.recommended_actions,
                "weather": {
                    "temperature_f": self._weather_data.temperature_f,
                    "humidity": self._weather_data.humidity,
                    "description": self._weather_data.description,
                },
                "ercot": {
                    "load_pct": self._ercot_data.load_capacity_pct,
                    "lmp_price": self._ercot_data.lmp_price,
                    "grid_alert": self._ercot_data.grid_alert_level,
                },
            })

            # Broadcast to WebSocket (reuse threat_level_str and threat_type_str from above)
            await ws_manager.broadcast("threat_assessment", {
                "threat_level": threat_level_str,
                "threat_type": threat_type_str,
                "urgency_score": assessment.urgency_score,
                "summary": assessment.summary,
                "reasoning": assessment.reasoning,
                "recommended_actions": assessment.recommended_actions,
            })

            # Automatically trigger orchestrator for HIGH/CRITICAL threats
            # This ensures voice alerts and permission requests happen immediately
            # Check if threat_level is HIGH or CRITICAL (handle both enum and string)
            is_high_or_critical = False
            if hasattr(assessment.threat_level, 'value'):
                is_high_or_critical = assessment.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL)
                logger.debug(f"Threat level check (enum): {assessment.threat_level} -> {is_high_or_critical}")
            else:
                threat_level_lower = str(assessment.threat_level).lower()
                is_high_or_critical = threat_level_lower in ('high', 'critical')
                logger.debug(f"Threat level check (string): {threat_level_lower} -> {is_high_or_critical}")

            if is_high_or_critical:
                logger.info(f"Triggering orchestrator for {threat_level_str} threat: {assessment.summary}")
                try:
                    from src.agents.orchestrator import orchestrator
                    # Trigger orchestrator to handle the threat (voice alert + permission)
                    await orchestrator.handle_threat_assessment(assessment)
                    logger.info("Orchestrator threat handling completed")
                except Exception as e:
                    logger.error(f"Failed to trigger orchestrator for threat: {e}", exc_info=True)
            else:
                logger.debug(f"Threat level {threat_level_str} is not HIGH/CRITICAL, skipping orchestrator trigger")

            self._record_action(
                action=f"Assessment: {threat_level_str} - {threat_type_str}",
                reasoning=assessment.reasoning[:500],
            )

            self._status = AgentStatus.IDLE
            return assessment

        except Exception as e:
            logger.error(f"Threat assessment error: {e}", exc_info=True)
            self._status = AgentStatus.ERROR
            self._error = str(e)
            return ThreatAssessment()

    async def _analyze_threats(self, weather: WeatherData, ercot: ERCOTData) -> ThreatAssessment:
        """Use LLM to synthesize data into a threat assessment."""
        prompt = THREAT_ANALYSIS_PROMPT.format(
            temp_f=weather.temperature_f,
            feels_like_f=weather.feels_like_f,
            humidity=weather.humidity,
            wind_mph=weather.wind_speed_mph,
            description=weather.description,
            forecast_high=weather.forecast_high_f,
            forecast_low=weather.forecast_low_f,
            alerts=", ".join(weather.alerts) if weather.alerts else "None",
            load_mw=ercot.system_load_mw,
            load_pct=ercot.load_capacity_pct,
            lmp=ercot.lmp_price,
            reserves_mw=ercot.operating_reserves_mw,
            grid_alert=ercot.grid_alert_level,
        )

        try:
            result = await llm_client.chat_json(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )

            if "error" in result:
                # LLM failed, use rule-based fallback
                return self._rule_based_assessment(weather, ercot)

            # Sanitize threat_type: LLM sometimes returns pipe-separated values
            raw_type = result.get("threat_type", "none")
            if "|" in raw_type:
                raw_type = raw_type.split("|")[0].strip()
            # Validate against enum
            try:
                threat_type = ThreatType(raw_type)
            except ValueError:
                logger.warning(f"Invalid threat_type '{raw_type}', defaulting to none")
                threat_type = ThreatType.NONE

            # Sanitize threat_level similarly
            raw_level = result.get("threat_level", "none")
            if "|" in raw_level:
                raw_level = raw_level.split("|")[0].strip()
            try:
                threat_level = ThreatLevel(raw_level)
            except ValueError:
                threat_level = ThreatLevel.NONE

            return ThreatAssessment(
                threat_level=threat_level,
                threat_type=threat_type,
                urgency_score=min(1.0, max(0.0, float(result.get("urgency_score", 0)))),
                summary=result.get("summary", ""),
                reasoning=result.get("reasoning", ""),
                recommended_actions=result.get("recommended_actions", []),
                weather_data=weather,
                ercot_data=ercot,
            )

        except Exception as e:
            logger.warning(f"LLM analysis failed, using rules: {e}")
            return self._rule_based_assessment(weather, ercot)

    def _rule_based_assessment(self, weather: WeatherData, ercot: ERCOTData) -> ThreatAssessment:
        """Fallback rule-based threat assessment when LLM is unavailable."""
        threat_level = ThreatLevel.NONE
        threat_type = ThreatType.NONE
        urgency = 0.0
        actions = []
        reasons = []

        # Heat wave check
        if weather.temperature_f > 105:
            threat_level = ThreatLevel.CRITICAL
            threat_type = ThreatType.HEAT_WAVE
            urgency = 0.95
            actions = ["pre_cool_home", "charge_battery", "close_blinds"]
            reasons.append(f"Extreme heat: {weather.temperature_f}°F")
        elif weather.temperature_f > 100:
            threat_level = ThreatLevel.HIGH
            threat_type = ThreatType.HEAT_WAVE
            urgency = 0.7
            actions = ["pre_cool_home", "set_eco_mode"]
            reasons.append(f"Heat wave: {weather.temperature_f}°F")

        # Cold snap check
        elif weather.temperature_f < 20:
            threat_level = ThreatLevel.CRITICAL
            threat_type = ThreatType.COLD_SNAP
            urgency = 0.9
            actions = ["increase_heating", "insulate_pipes_alert"]
            reasons.append(f"Extreme cold: {weather.temperature_f}°F")
        elif weather.temperature_f < 32:
            threat_level = ThreatLevel.HIGH
            threat_type = ThreatType.COLD_SNAP
            urgency = 0.6
            actions = ["increase_heating"]
            reasons.append(f"Freezing temps: {weather.temperature_f}°F")

        # Grid strain check
        if ercot.load_capacity_pct > 95:
            # Compare threat levels: CRITICAL > HIGH > MEDIUM > LOW > NONE
            threat_level_order = {ThreatLevel.NONE: 0, ThreatLevel.LOW: 1, ThreatLevel.MEDIUM: 2, ThreatLevel.HIGH: 3, ThreatLevel.CRITICAL: 4}
            if threat_level_order.get(threat_level, 0) < threat_level_order[ThreatLevel.CRITICAL]:
                threat_level = ThreatLevel.CRITICAL
            threat_type = ThreatType.GRID_STRAIN
            urgency = max(urgency, 0.95)
            actions.extend(["reduce_consumption", "switch_to_battery"])
            reasons.append(f"Grid at {ercot.load_capacity_pct}% capacity")
        elif ercot.load_capacity_pct > 85:
            # Compare threat levels: only upgrade if current is below HIGH
            threat_level_order = {ThreatLevel.NONE: 0, ThreatLevel.LOW: 1, ThreatLevel.MEDIUM: 2, ThreatLevel.HIGH: 3, ThreatLevel.CRITICAL: 4}
            if threat_level_order.get(threat_level, 0) < threat_level_order[ThreatLevel.HIGH]:
                threat_level = ThreatLevel.HIGH
                threat_type = ThreatType.GRID_STRAIN
            urgency = max(urgency, 0.7)
            actions.append("reduce_non_essential")
            reasons.append(f"Grid strain: {ercot.load_capacity_pct}% capacity")

        # High price check
        if ercot.lmp_price > 100:
            actions.append("defer_high_energy_tasks")
            reasons.append(f"High energy price: ${ercot.lmp_price}/MWh")

        return ThreatAssessment(
            threat_level=threat_level,
            threat_type=threat_type,
            urgency_score=urgency,
            summary="; ".join(reasons) if reasons else "No threats detected",
            reasoning="Rule-based assessment: " + "; ".join(reasons) if reasons else "All conditions normal",
            recommended_actions=actions,
            weather_data=weather,
            ercot_data=ercot,
        )


# Singleton
threat_agent = ThreatAssessmentAgent()
