import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
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

app = FastAPI(title="MediRoute API", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://mediroute-frontend-xgzj.onrender.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
