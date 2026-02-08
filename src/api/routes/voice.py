"""Voice alert API routes."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.agents.voice import voice_agent

router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceAlertRequest(BaseModel):
    message: str
    require_permission: bool = False


class PermissionResponse(BaseModel):
    alert_id: str
    approved: bool | None = None  # Optional - can be inferred from user_text
    user_text: str = ""  # Natural language response (e.g., "yes", "only turn up the heat")
    modifications: dict = {}  # Legacy field, kept for backwards compatibility


@router.post("/alert")
async def send_voice_alert(req: VoiceAlertRequest) -> dict[str, Any]:
    """Send a voice alert to the user."""
    result = await voice_agent.run(
        message=req.message,
        require_permission=req.require_permission,
    )
    return result


@router.post("/permission")
async def respond_to_permission(req: PermissionResponse) -> dict[str, Any]:
    """Respond to a permission request with natural language support.
    
    Can accept either:
    - approved: bool (simple yes/no)
    - user_text: str (natural language like "only turn up the heat")
    
    Returns:
        dict with 'success' (bool) and optionally 'error_message' (str) if clarity check fails
    """
    result = await voice_agent.handle_permission_response(
        alert_id=req.alert_id,
        approved=req.approved,
        user_text=req.user_text,
        modifications=req.modifications,
    )
    return result


@router.get("/history")
async def get_alert_history() -> list[dict[str, Any]]:
    """Get voice alert history."""
    return [
        {k: v for k, v in alert.items() if k != "audio_base64"}
        for alert in voice_agent.alert_history
    ]


@router.get("/pending")
async def get_pending_permissions() -> dict[str, Any]:
    """Get count of pending permission requests."""
    return {"pending_count": voice_agent.pending_count}
