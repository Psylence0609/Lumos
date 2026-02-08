"""OpenWeatherMap API client for current weather and forecast data."""

import logging
from datetime import datetime

import httpx

from config import settings
from src.models.threat import WeatherData

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openweathermap.org/data/2.5"


class OpenWeatherClient:
    """Client for OpenWeatherMap free tier API."""

    def __init__(self):
        self._api_key = settings.openweathermap_api_key
        self._lat = settings.home_latitude
        self._lon = settings.home_longitude
        self._client = httpx.AsyncClient(timeout=10.0)
        self._override: WeatherData | None = None

    def set_override(self, data: WeatherData) -> None:
        """Set simulation override for weather data."""
        self._override = data

    def clear_override(self) -> None:
        """Clear simulation override."""
        self._override = None

    async def get_current_weather(self) -> WeatherData:
        """Fetch current weather conditions."""
        if self._override:
            return self._override

        if not self._api_key or self._api_key == "your_openweathermap_api_key_here":
            logger.warning("OpenWeatherMap API key not configured, returning defaults")
            return WeatherData()

        try:
            resp = await self._client.get(
                f"{BASE_URL}/weather",
                params={
                    "lat": self._lat,
                    "lon": self._lon,
                    "appid": self._api_key,
                    "units": "imperial",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            return WeatherData(
                temperature_f=data["main"]["temp"],
                feels_like_f=data["main"]["feels_like"],
                humidity=data["main"]["humidity"],
                wind_speed_mph=data["wind"]["speed"],
                description=data["weather"][0]["description"] if data.get("weather") else "",
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"OpenWeatherMap API error: {e}")
            return WeatherData()

    async def get_forecast(self) -> WeatherData:
        """Fetch 5-day forecast and extract highs/lows and alerts."""
        if self._override:
            return self._override

        if not self._api_key or self._api_key == "your_openweathermap_api_key_here":
            return WeatherData()

        try:
            # Current weather
            current = await self.get_current_weather()

            # 5-day forecast
            resp = await self._client.get(
                f"{BASE_URL}/forecast",
                params={
                    "lat": self._lat,
                    "lon": self._lon,
                    "appid": self._api_key,
                    "units": "imperial",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            # Extract today's high/low from forecast
            today = datetime.now().date()
            temps = []
            for item in data.get("list", []):
                dt = datetime.fromtimestamp(item["dt"])
                if dt.date() == today:
                    temps.append(item["main"]["temp"])

            if temps:
                current.forecast_high_f = max(temps)
                current.forecast_low_f = min(temps)

            # Check for weather alerts (using OneCall API if available)
            # Free tier uses basic endpoints; alerts parsed from description
            alerts = []
            for item in data.get("list", [])[:8]:  # Next 24 hours
                desc = item["weather"][0]["description"] if item.get("weather") else ""
                if any(w in desc.lower() for w in ["storm", "thunder", "tornado", "hurricane"]):
                    alerts.append(desc)
            current.alerts = list(set(alerts))

            return current

        except Exception as e:
            logger.error(f"OpenWeatherMap forecast error: {e}")
            return WeatherData()

    async def close(self) -> None:
        await self._client.aclose()


# Singleton
weather_client = OpenWeatherClient()
