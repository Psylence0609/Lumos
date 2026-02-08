"""Pattern detection API routes."""

from typing import Any

from fastapi import APIRouter, HTTPException

from src.agents.pattern_detector import pattern_agent

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.get("")
async def list_patterns() -> list[dict[str, Any]]:
    """Get all detected patterns."""
    return [
        {
            "pattern_id": p.pattern_id,
            "type": p.pattern_type.value,
            "name": p.display_name,
            "description": p.description,
            "frequency": p.frequency,
            "confidence": p.confidence,
            "approved": p.approved,
            "ready_to_suggest": p.is_ready_to_suggest(),
            "actions": [a.model_dump() for a in p.action_sequence],
            "trigger_conditions": p.trigger_conditions,
            "source_utterance": p.source_utterance,
            "last_occurrence": p.last_occurrence.isoformat(),
            "created_at": p.created_at.isoformat(),
        }
        for p in pattern_agent.patterns.values()
    ]


@router.post("/{pattern_id}/approve")
async def approve_pattern(pattern_id: str) -> dict[str, Any]:
    """Approve a detected pattern for automation."""
    success = await pattern_agent.approve_pattern(pattern_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pattern not found: {pattern_id}")
    return {"pattern_id": pattern_id, "approved": True}


@router.post("/{pattern_id}/dismiss")
async def dismiss_pattern(pattern_id: str) -> dict[str, Any]:
    """Dismiss a detected pattern."""
    success = await pattern_agent.dismiss_pattern(pattern_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Pattern not found: {pattern_id}")
    return {"pattern_id": pattern_id, "dismissed": True}


@router.post("/analyze")
async def trigger_analysis() -> dict[str, Any]:
    """Manually trigger pattern analysis."""
    patterns = await pattern_agent.run()
    return {"patterns_found": len(patterns)}
