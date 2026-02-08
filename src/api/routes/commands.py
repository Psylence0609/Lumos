"""Natural language command API routes."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from src.agents.orchestrator import orchestrator
from src.agents.voice import voice_agent

router = APIRouter(prefix="/commands", tags=["commands"])


class CommandRequest(BaseModel):
    command: str
    source: str = "text"  # "text" or "voice"


@router.post("")
async def submit_command(req: CommandRequest) -> dict[str, Any]:
    """Submit a natural language command to the orchestrator.

    If the source is "voice", run a clarity check first — if the
    transcription is gibberish, ask the user to repeat.
    Audio feedback is always provided for voice commands.
    """
    command = req.command.strip()

    # Basic sanity checks for voice input
    if req.source == "voice":
        # Too short or empty
        if len(command) < 3:
            msg = "I didn't catch that. Could you hold the mic button and try again, or type your request?"
            # Generate TTS so the user hears the feedback
            await voice_agent.run(message=msg, require_permission=False)
            return {
                "success": False,
                "unclear": True,
                "message": msg,
            }

        # Run LLM clarity check for voice-transcribed text
        clarity = await orchestrator.check_command_clarity(command)
        if not clarity["is_clear"]:
            msg = clarity.get("message", "That wasn't clear. Please try again or type your request.")
            # Generate TTS so the user hears the feedback
            await voice_agent.run(message=msg, require_permission=False)
            return {
                "success": False,
                "unclear": True,
                "message": msg,
            }

        # Use cleaned text from clarity check
        command = clarity.get("cleaned_text", command)

    result = await orchestrator.handle_user_command(command, source=req.source)
    return result
