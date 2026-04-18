"""Replay service for decision debugging."""

from __future__ import annotations

from typing import Any

from db.connection import SessionLocal
from db.models import AuditLog
from core.dispatch_engine import run_dispatch


async def replay_case(case_id: str) -> dict[str, Any] | None:
    session = SessionLocal()
    try:
        case = session.query(AuditLog).filter(AuditLog.case_id == case_id).first()
        if case is None:
            return None

        original = {
            "case_id": case.case_id,
            "input": dict(case.input_payload or {}),
            "output": dict(case.output_payload or {}),
            "score": float(case.score or 0.0),
            "created_at": case.created_at.isoformat() if case.created_at else None,
        }
    finally:
        session.close()

    input_payload = dict(original.get("input") or {})
    if not input_payload:
        return {
            "original": original,
            "recomputed": None,
        }

    recomputed = await run_dispatch(
        case_id=input_payload.get("case_id"),
        hospitals=input_payload.get("hospitals") or [],
        ambulance_lat=float(input_payload.get("ambulance_lat", 0.0)),
        ambulance_lng=float(input_payload.get("ambulance_lng", 0.0)),
        condition_type=str(input_payload.get("condition_type", "general")),
        severity_score=input_payload.get("severity_score"),
        vitals=input_payload.get("vitals"),
        ambulance_equipment=input_payload.get("ambulance_equipment"),
        required_equipment=input_payload.get("required_equipment") or [],
        forced_hospital_types=set(input_payload.get("forced_hospital_types") or []) or None,
        force_direct=bool(input_payload.get("force_direct", False)),
        relax_important_constraints=bool(input_payload.get("relax_important_constraints", False)),
        enable_adaptive_constraints=bool(input_payload.get("enable_adaptive_constraints", True)),
        scenario_context=input_payload.get("scenario_context"),
    )

    return {
        "original": original,
        "recomputed": recomputed,
    }

