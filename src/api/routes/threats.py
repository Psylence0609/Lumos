"""Threat assessment API routes."""

from typing import Any

from fastapi import APIRouter

from src.agents.threat_assessment import threat_agent

router = APIRouter(prefix="/threats", tags=["threats"])


@router.get("/current")
async def get_current_threat() -> dict[str, Any]:
    """Get the latest threat assessment."""
    assessment = threat_agent.latest_assessment
    return {
        "threat_level": assessment.threat_level.value,
        "threat_type": assessment.threat_type.value,
        "urgency_score": assessment.urgency_score,
        "summary": assessment.summary,
        "reasoning": assessment.reasoning,
        "recommended_actions": assessment.recommended_actions,
        "timestamp": assessment.timestamp.isoformat(),
    }


@router.get("/weather")
async def get_weather_data() -> dict[str, Any]:
    """Get current weather data."""
    w = threat_agent.weather_data
    return {
        "temperature_f": w.temperature_f,
        "feels_like_f": w.feels_like_f,
        "humidity": w.humidity,
        "wind_speed_mph": w.wind_speed_mph,
        "description": w.description,
        "alerts": w.alerts,
        "forecast_high_f": w.forecast_high_f,
        "forecast_low_f": w.forecast_low_f,
    }


@router.get("/grid")
async def get_grid_data() -> dict[str, Any]:
    """Get current ERCOT grid conditions."""
    e = threat_agent.ercot_data
    return {
        "system_load_mw": e.system_load_mw,
        "load_capacity_pct": e.load_capacity_pct,
        "lmp_price": e.lmp_price,
        "operating_reserves_mw": e.operating_reserves_mw,
        "grid_alert_level": e.grid_alert_level,
    }


@router.post("/assess")
async def trigger_assessment() -> dict[str, Any]:
    """Manually trigger a new threat assessment."""
    assessment = await threat_agent.run()
    return {
        "threat_level": assessment.threat_level.value,
        "threat_type": assessment.threat_type.value,
        "summary": assessment.summary,
    }
