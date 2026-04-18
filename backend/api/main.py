"""
MediRoute — FastAPI application entry point
Run with:
    uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload
"""
import os
import logging

import redis as redis_lib
import psycopg2
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes.dispatch  import router as dispatch_router
from api.routes.analytics import router as analytics_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [api] %(levelname)s %(message)s",
)

app = FastAPI(title="MediRoute API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dispatch_router)
app.include_router(analytics_router)

REDIS_URL    = os.environ.get("REDIS_URL",    "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mediroute")


@app.get("/health")
def health():
    status = {"api": "ok", "redis": "error", "db": "error"}

    try:
        r = redis_lib.from_url(REDIS_URL)
        r.ping()
        status["redis"] = "ok"
    except Exception:
        pass

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.close()
        status["db"] = "ok"
    except Exception:
        pass

    return status
