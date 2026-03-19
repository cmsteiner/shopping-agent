"""
Application configuration loaded from environment variables using pydantic-settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Users
    chris_phone: str = "+15550000000"
    donna_phone: str = "+15550000001"

    # Webhook
    webhook_secret: str = ""

    # Database
    database_url: str = "sqlite:////data/shopping.db"

    # App
    environment: str = "development"
    duplicate_threshold: int = 85
    trip_timeout_hours: int = 8
    max_sms_chars: int = 1500

    # Models
    haiku_model: str = "claude-haiku-4-5-20251001"
    sonnet_model: str = "claude-sonnet-4-6"


settings = Settings()
