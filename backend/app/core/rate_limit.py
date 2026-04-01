"""
Rate limiting configuration for MediRoute API.
Uses slowapi to prevent brute-force attacks and API abuse.
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

# Disable rate limiting during tests
_enabled = os.environ.get("TESTING", "").lower() != "true"

limiter = Limiter(
    key_func=get_remote_address,
    enabled=_enabled,
)

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"}
    )
