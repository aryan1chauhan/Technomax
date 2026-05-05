"""Runtime settings scaffold."""

from __future__ import annotations

import os


class Settings:
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    redis_url: str | None = os.getenv("REDIS_URL")


settings = Settings()
