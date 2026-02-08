"""Authentication API routes."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.integrations.google_calendar import calendar_client

router = APIRouter(prefix="/auth", tags=["auth"])


class GoogleTokenRequest(BaseModel):
    access_token: str
    expires_in: int = 3600


@router.post("/google-token")
async def set_google_token(req: GoogleTokenRequest) -> dict[str, Any]:
    """Receive Google OAuth token from frontend and initialize Calendar client.
    
    This allows the frontend to handle OAuth and pass the token to the backend
    for Calendar API access.
    """
    try:
        # Initialize calendar client with the token from frontend
        success = await calendar_client.initialize_with_token(
            access_token=req.access_token,
            expires_in=req.expires_in,
        )
        
        if success:
            return {"success": True, "message": "Google Calendar token set successfully"}
        else:
            return {"success": False, "message": "Failed to initialize Calendar client"}
    except Exception as e:
        return {"success": False, "error": str(e)}
