from pydantic_settings import BaseSettings
from pydantic import ConfigDict

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    claude_api_key: str | None = None
    gemini_api_key: str | None = None
    ors_api_key: str | None = None
    firebase_service_account_path: str | None = None
    webhook_delivery_url: str | None = None
    webhook_secret: str = "change-me-webhook-secret"
    webhook_max_attempts: int = 4
    webhook_base_backoff_seconds: float = 0.5
    webhook_timeout_seconds: float = 5.0
    sms_fallback_number: str | None = None
    sms_timeout_seconds: float = 3.0

settings = Settings()
