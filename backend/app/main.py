from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import engine, get_db
from app.db import models
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.hospitals import router as hospitals_router
from app.api.endpoints.dispatch import router as dispatch_router
from app.api.endpoints.cases import router as cases_router
from app.api.endpoints.ai import router as ai_router
from app.api.endpoints import tracking

app = FastAPI(title="MediRoute API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

models.Base.metadata.create_all(bind=engine)

app.include_router(auth_router)
app.include_router(hospitals_router)
app.include_router(dispatch_router)
app.include_router(cases_router)
app.include_router(ai_router)
app.include_router(tracking.router)

@app.get("/")
def read_root():
    return {"status": "MediRoute API is running"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check for container orchestration (Docker, K8s)."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": str(e)}

