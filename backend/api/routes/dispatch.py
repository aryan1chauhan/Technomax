"""
MediRoute — /dispatch route
KEY CHANGE vs legacy: uses rq.Queue.enqueue() instead of raw Redis lpush.

Why this matters:
  lpush → puts a bare string on the list.  RQ worker cannot deserialise it.
  rq.Queue.enqueue() → wraps the job in RQ's JSON envelope (job_id, func path,
  args, created_at, ttl …) so the worker can pick it up, execute it, and
  report success/failure through rq:job:<id> keys.
"""
from __future__ import annotations

import os
import uuid
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import redis
from rq import Queue

from api.scoring import select_best_hospital, vitals_decision
from worker.tasks import audit_log  # imported by reference — RQ serialises the path

log = logging.getLogger(__name__)

router = APIRouter()

# ── Redis / RQ setup ──────────────────────────────────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

def _get_queue() -> Queue:
    """Fresh Redis connection per request — safe under uvicorn workers."""
    conn = redis.from_url(REDIS_URL)
    return Queue("mediroute", connection=conn)


# ── Request / Response models ─────────────────────────────────────────────────
class HospitalIn(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    available_beds: int
    total_beds: int
    icu_beds: int = 0
    has_icu: bool = False
    accepting: bool = True
    hospital_type: str = "secondary"
    equipment: list[str] = Field(default_factory=list)
    hospital_load: float = 0.5
    # these come from the client pre-scored; we ignore and re-score server-side
    score: float = 0.0
    score_breakdown: dict = Field(default_factory=dict)


class DispatchRequest(BaseModel):
    hospitals: list[HospitalIn]
    ambulance_lat: float
    ambulance_lng: float
    condition_type: str = "default"
    severity_score: int = Field(default=5, ge=1, le=10)
    required_equipment: list[str] = Field(default_factory=list)
    ambulance_equipment: list[str] = Field(default_factory=list)
    vitals: dict[str, Any] = Field(default_factory=dict)


class DispatchResponse(BaseModel):
    case_id: str
    decision: str
    reasoning: list[str]
    selected_hospital: dict | None
    job_id: str                   # RQ job ID — use for /replay lookup
    queued: bool


# ── Endpoint ──────────────────────────────────────────────────────────────────
@router.post("/dispatch", response_model=DispatchResponse)
async def dispatch(req: DispatchRequest):
    case_id = str(uuid.uuid4())
    log.info("dispatch | case_id=%s condition=%s severity=%d",
             case_id, req.condition_type, req.severity_score)

    if not req.hospitals:
        raise HTTPException(status_code=400, detail="No hospitals provided")

    # 1. Vitals check
    decision, reasons = vitals_decision(req.vitals)

    # 2. Score hospitals and pick best
    hospitals_raw = [h.model_dump() for h in req.hospitals]
    best = select_best_hospital(
        hospitals_raw,
        req.ambulance_lat, req.ambulance_lng,
        req.condition_type, req.severity_score,
        req.required_equipment,
    )

    if best is None:
        raise HTTPException(status_code=422, detail="No eligible hospital found")

    log.info("dispatch | selected=%s score=%.1f decision=%s",
             best["name"], best["score"], decision)

    # 3. Build audit payload
    audit_payload = {
        "case_id":                case_id,
        "condition_type":         req.condition_type,
        "severity_score":         req.severity_score,
        "ambulance_lat":          req.ambulance_lat,
        "ambulance_lng":          req.ambulance_lng,
        "selected_hospital_id":   best["id"],
        "selected_hospital_name": best["name"],
        "score":                  best["score"],
        "score_breakdown":        best["score_breakdown"],
        "vitals":                 req.vitals,
        "required_equipment":     req.required_equipment,
        "ambulance_equipment":    req.ambulance_equipment,
        "all_hospitals":          hospitals_raw,
    }

    # 4. Enqueue via RQ (not lpush) ← THE FIX
    queued   = False
    job_id   = "unavailable"
    try:
        q      = _get_queue()
        job    = q.enqueue(
            audit_log,
            audit_payload,
            job_timeout=30,
            result_ttl=3600,    # keep result 1 hr for /replay
        )
        job_id = job.id
        queued = True
        log.info("dispatch | enqueued job_id=%s queue=mediroute", job_id)
    except Exception as e:
        # Non-fatal: respond to ambulance, log the failure
        log.error("dispatch | queue error (audit will be lost): %s", e)

    return DispatchResponse(
        case_id=case_id,
        decision=decision,
        reasoning=reasons or [f"Vitals stable — routing to {best['name']}"],
        selected_hospital=best,
        job_id=job_id,
        queued=queued,
    )
