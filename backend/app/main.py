import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.hospitals import router as hospitals_router
from app.api.endpoints.dispatch import router as dispatch_router
from app.api.endpoints.cases import router as cases_router
from app.api.endpoints.ai import router as ai_router
from app.api.endpoints.voice import router as voice_router
from app.api.endpoints.users import router as users_router
from app.api.endpoints import tracking
from app.core.config import settings
from app.services.eta_service import set_haversine_only_mode

if settings.deterministic_eta:
    set_haversine_only_mode(True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Align thread pool to per-worker DB connection ceiling: pool_size(8) + max_overflow(4) = 12
    # At 8 Uvicorn workers: 8 × 12 = 96 total connections (< PG max_connections=100)
    # Prevents threads from queueing for connections under sustained load.
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=20))
    yield
    # Shutdown cleanup (add resource teardown here if needed)

# ---------------------------------------------------------------------------
# Docs are only exposed when ENVIRONMENT != production
# Set ENVIRONMENT=production in Render env vars.
# ---------------------------------------------------------------------------
_env = os.getenv("ENVIRONMENT", "development")
_is_prod = _env == "production"
_docs_url  = None if _is_prod else "/docs"
_redoc_url = None if _is_prod else "/redoc"

app = FastAPI(
    title="MediRoute API",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ---------------------------------------------------------------------------
# CORS — localhost origins only allowed outside production
# ---------------------------------------------------------------------------
_cors_origins = ["https://technomax-1.onrender.com"]
if not _is_prod:
    _cors_origins += ["http://localhost:5173", "http://localhost:3000"]

# Allow additional origins via comma-separated env var (e.g. custom domain)
_extra = os.getenv("CORS_ALLOWED_ORIGINS", "")
if _extra:
    _cors_origins += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Security response headers
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]        = "DENY"
    response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    if _is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

app.include_router(auth_router)
app.include_router(hospitals_router)
app.include_router(dispatch_router)
app.include_router(cases_router)
app.include_router(ai_router)
app.include_router(voice_router)
app.include_router(users_router)
app.include_router(tracking.router)

@app.get("/")
def read_root():
    return {"status": "MediRoute API is running"}

@app.get("/health")
def health_check():
    """Liveness probe — always fast, no DB connection consumed.
    Used by Docker HEALTHCHECK and nginx upstream health polling."""
    return {"status": "ok"}

@app.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    """Readiness probe — confirms DB connectivity before receiving traffic.
    Call manually after restart; not in the hot path."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": str(e)}
