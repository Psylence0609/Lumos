"""OpenRouter LLM client with multi-model support and fallback."""

import json
import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class OpenRouterClient:
    """Client for OpenRouter API with multi-model fallback."""

    def __init__(self):
        self._api_key = settings.openrouter_api_key
        self._base_url = settings.openrouter_base_url
        self._default_model = settings.openrouter_default_model
        self._fallback_models = settings.openrouter_fallback_models
        self._client = httpx.AsyncClient(timeout=30.0)
        self._request_count = 0

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: dict | None = None,
    ) -> str:
        """Send a chat completion request with automatic fallback."""
        models_to_try = [model or self._default_model] + self._fallback_models

        for m in models_to_try:
            try:
                result = await self._send_request(
                    m, messages, temperature, max_tokens, response_format
                )
                return result
            except Exception as e:
                logger.warning(f"Model {m} failed: {e}")
                continue

        logger.error("All models failed")
        return '{"error": "All LLM models unavailable"}'

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> dict[str, Any]:
        """Send a chat request and parse JSON response."""
        response = await self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Try to parse JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response: {response[:200]}")
            return {"error": "Failed to parse response", "raw": response[:500]}

    async def _send_request(
        self,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        response_format: dict | None = None,
    ) -> str:
        """Send a single request to OpenRouter."""
        if not self._api_key or self._api_key == "your_openrouter_api_key_here":
            raise ValueError("OpenRouter API key not configured")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Smart Home Agent",
        }

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            body["response_format"] = response_format

        resp = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

        self._request_count += 1
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")

        logger.debug(f"OpenRouter [{model}] response: {content[:100]}...")
        return content

    @property
    def request_count(self) -> int:
        return self._request_count

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
llm_client = OpenRouterClient()
