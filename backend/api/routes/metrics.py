"""Metrics API endpoint for observability summary."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from db.connection import SessionLocal
from db.models import AuditLog


router = APIRouter()
RECENT_WINDOW_SIZE = 100


@router.get("/metrics")
def get_metrics() -> dict[str, object]:
    session = SessionLocal()
    try:
        total_cases = int(session.query(func.count(AuditLog.case_id)).scalar() or 0)
        overall_mean_raw = session.query(func.avg(AuditLog.score)).scalar()
        overall_mean_score = float(overall_mean_raw) if overall_mean_raw is not None else 0.0

        recent_rows = (
            session.query(AuditLog.score)
            .order_by(AuditLog.created_at.desc())
            .limit(RECENT_WINDOW_SIZE)
            .all()
        )
        recent_scores = [float(row[0]) for row in recent_rows if row and row[0] is not None]
        recent_count = len(recent_scores)
        recent_mean_score = (sum(recent_scores) / recent_count) if recent_count > 0 else 0.0

        return {
            "total_cases": recent_count,
            "mean_score": recent_mean_score,
            "failures": {},
            "window_size": RECENT_WINDOW_SIZE,
            "overall_total_cases": total_cases,
            "overall_mean_score": overall_mean_score,
        }
    except SQLAlchemyError:
        return {
            "total_cases": 0,
            "mean_score": 0.0,
            "failures": {},
            "window_size": RECENT_WINDOW_SIZE,
            "overall_total_cases": 0,
            "overall_mean_score": 0.0,
        }
    finally:
        session.close()

