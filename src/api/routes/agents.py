"""Agent status and control API routes."""

from typing import Any

from fastapi import APIRouter

from src.agents.orchestrator import orchestrator

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents() -> list[dict[str, Any]]:
    """Get status of all agents."""
    return orchestrator.get_all_agent_info()


@router.get("/{agent_id}")
async def get_agent(agent_id: str) -> dict[str, Any]:
    """Get status of a specific agent."""
    for info in orchestrator.get_all_agent_info():
        if info["agent_id"] == agent_id:
            return info
    return {"error": f"Agent not found: {agent_id}"}


@router.get("/decisions/history")
async def get_decision_history() -> list[dict[str, Any]]:
    """Get orchestrator decision history."""
    return orchestrator.decision_history
