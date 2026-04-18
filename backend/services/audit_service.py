"""Audit persistence helpers backed by SQLAlchemy."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from db.connection import SessionLocal
from db.models import AuditLog


def _extract_score_from_output(output_payload: dict[str, Any]) -> float:
    score = output_payload.get("final_score")
    if score is None:
        score = (output_payload.get("reasoning") or {}).get("ml_score", 0.0)

    try:
        return float(score)
    except (TypeError, ValueError):
        return 0.0


def store_case(case_id: str, data: dict[str, Any]) -> bool:
    if not case_id:
        return False

    session = SessionLocal()
    try:
        input_payload = dict(data.get("input") or {})
        output_payload = dict(data.get("output") or {})
        score = _extract_score_from_output(output_payload)

        log = AuditLog(
            case_id=case_id,
            input_payload=input_payload,
            output_payload=output_payload,
            score=score,
        )
        session.merge(log)
        session.commit()
        return True
    except SQLAlchemyError:
        session.rollback()
        return False
    finally:
        session.close()


def load_case(case_id: str) -> dict[str, Any] | None:
    session = SessionLocal()
    try:
        row = session.query(AuditLog).filter(AuditLog.case_id == case_id).first()
        if row is None:
            return None
        return {
            "case_id": row.case_id,
            "input": dict(row.input_payload or {}),
            "output": dict(row.output_payload or {}),
            "score": float(row.score or 0.0),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
    finally:
        session.close()

