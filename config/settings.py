"""Central configuration using Pydantic BaseSettings."""

from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # OpenRouter
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "openai/gpt-4o-mini"
    openrouter_fallback_models: list[str] = []

    # ElevenLabs
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice

    # OpenWeatherMap
    openweathermap_api_key: str = Field(default="", alias="OPENWEATHERMAP_API_KEY")
    weather_poll_interval_seconds: int = 300  # 5 minutes

    # Google Calendar
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")

    # MQTT
    mqtt_host: str = Field(default="localhost", alias="MQTT_HOST")
    mqtt_port: int = Field(default=1883, alias="MQTT_PORT")

    # Location
    home_latitude: float = Field(default=30.2672, alias="HOME_LATITUDE")
    home_longitude: float = Field(default=-97.7431, alias="HOME_LONGITUDE")
    geofence_radius_meters: float = 200.0

    # ERCOT
    ercot_poll_interval_seconds: int = 120  # 2 minutes

    # Application
    app_name: str = "Smart Home Agent System"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Storage
    chroma_persist_dir: str = ".chroma"
    sqlite_db_path: str = "smarthome.db"

    # Devices config
    devices_config_path: str = str(
        Path(__file__).parent / "devices.yaml"
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
