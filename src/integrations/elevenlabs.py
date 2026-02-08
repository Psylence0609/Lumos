"""ElevenLabs TTS client for voice alerts."""

import io
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"


class ElevenLabsClient:
    """Client for ElevenLabs text-to-speech API."""

    def __init__(self):
        self._api_key = settings.elevenlabs_api_key
        self._voice_id = settings.elevenlabs_voice_id
        self._client = httpx.AsyncClient(timeout=30.0)

    async def text_to_speech(
        self,
        text: str,
        voice_id: str | None = None,
        model_id: str = "eleven_monolingual_v1",
    ) -> bytes | None:
        """Convert text to speech audio bytes (MP3).

        Returns MP3 audio bytes or None on failure.
        """
        if not self._api_key or self._api_key == "your_elevenlabs_api_key_here":
            logger.warning("ElevenLabs API key not configured")
            return None

        vid = voice_id or self._voice_id

        try:
            resp = await self._client.post(
                f"{ELEVENLABS_API_URL}/text-to-speech/{vid}",
                headers={
                    "xi-api-key": self._api_key,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg",
                },
                json={
                    "text": text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75,
                    },
                },
            )
            resp.raise_for_status()
            logger.info(f"Generated TTS audio ({len(resp.content)} bytes)")
            return resp.content

        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            return None

    async def get_voices(self) -> list[dict]:
        """List available voices."""
        if not self._api_key or self._api_key == "your_elevenlabs_api_key_here":
            return []

        try:
            resp = await self._client.get(
                f"{ELEVENLABS_API_URL}/voices",
                headers={"xi-api-key": self._api_key},
            )
            resp.raise_for_status()
            return resp.json().get("voices", [])
        except Exception as e:
            logger.error(f"ElevenLabs voices error: {e}")
            return []

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
tts_client = ElevenLabsClient()
