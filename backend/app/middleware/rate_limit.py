"""
app/middleware/rate_limit.py
----------------------------
Centralised rate-limit configuration for MediRoute.

Usage
-----
In main.py / app factory:

    from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

Then decorate endpoints:

    from app.middleware.rate_limit import limiter
    from fastapi import Request

    @router.post("/dispatch")
    @limiter.limit("10/minute")
    async def dispatch(request: Request, ...):
        ...

Notes
-----
- Key function defaults to client IP.  Behind a proxy (Nginx / Render) the
  real IP is read from X-Forwarded-For automatically by slowapi.
- In tests, override with:  limiter._key_func = lambda r: "test-client"
- All limits are env-configurable so staging/prod can differ without a code
  change.
"""

from __future__ import annotations

import os
import logging
import time
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


def _key_func(request: Request) -> str:
    """
    Client key for throttling.
    - Uses X-Forwarded-For first for reverse-proxy deployments.
    - Falls back to remote address.
    - Disables effective throttling in tests when TESTING=true.
    """
    if os.getenv("TESTING", "").lower() == "true":
        return f"test-{time.time_ns()}"

    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()

    return get_remote_address(request)

# ---------------------------------------------------------------------------
# Per-route limit strings (overridable via environment variables)
# ---------------------------------------------------------------------------

# Auth endpoints – brute-force protection
LIMIT_AUTH_LOGIN    = os.getenv("RATELIMIT_AUTH_LOGIN",    "10/minute")
LIMIT_AUTH_REGISTER = os.getenv("RATELIMIT_AUTH_REGISTER", "5/minute")

# Core dispatch – prevent DB / ML engine exhaustion
LIMIT_DISPATCH      = os.getenv("RATELIMIT_DISPATCH",      "10/minute")

# AI parser – protects Anthropic API credit burn
LIMIT_AI            = os.getenv("RATELIMIT_AI",            "20/minute")

# Hospital read endpoints – read-heavy but still bounded
LIMIT_HOSPITALS_READ  = os.getenv("RATELIMIT_HOSPITALS_READ",  "60/minute")
LIMIT_HOSPITALS_WRITE = os.getenv("RATELIMIT_HOSPITALS_WRITE", "20/minute")

# Case tracking – moderate
LIMIT_CASES         = os.getenv("RATELIMIT_CASES",         "30/minute")

# Generic fallback applied to any un-decorated route via SlowAPIMiddleware
LIMIT_DEFAULT       = os.getenv("RATELIMIT_DEFAULT",       "100/minute")

# ---------------------------------------------------------------------------
# Limiter instance
# ---------------------------------------------------------------------------

limiter = Limiter(
    key_func=_key_func,
    default_limits=[LIMIT_DEFAULT],
    # Store in-memory by default; swap to Redis with:
    #   storage_uri="redis://localhost:6379"
    # (aligns with the Redis pub/sub roadmap item)
    storage_uri=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
)

# ---------------------------------------------------------------------------
# Custom 429 handler — returns JSON (not HTML) so the React UI never breaks
# ---------------------------------------------------------------------------

async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    logger.warning(
        "Rate limit exceeded | ip=%s path=%s limit=%s",
        _key_func(request),
        request.url.path,
        exc.limit,
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests. Please slow down.",
            "limit": str(exc.limit),
            "path": request.url.path,
        },
        headers={"Retry-After": "60"},
    )
