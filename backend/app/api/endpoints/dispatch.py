"""
dispatch.py — Enriched dispatch endpoint.

Key changes from original:
- Calls score_hospitals() from new transparent scorer
- Returns ScoredHospitalResponse + alternatives + rejected_hospitals
- Keeps all legacy flat fields derived from selected_hospital
- Beds are decremented atomically; restored on cancel/complete (cases.py)
- Graceful no_match handling with fallback suggestions
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.db.models import Case, User, Availability, CaseEvent
from datetime import datetime, timezone
from app.schemas.dispatch import (
    DispatchRequest, DispatchResponse,
    ScoredHospitalResponse, RejectionSummary,
)
from app.core.security import get_current_user
from app.engine.ml_scorer import score_hospitals, SEVERITY_MAP
from app.engine.haversine import calculate_distance

import asyncio
import json
import httpx
import logging
from app.core.config import settings


router = APIRouter(prefix="/api/dispatch")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _scored_to_response(s) -> ScoredHospitalResponse:
    """Convert ScoredHospital dataclass → Pydantic response model."""
    return ScoredHospitalResponse(
        hospital_id=s.hospital_id,
        name=s.name,
        distance_km=s.distance_km,
        available_beds=s.available_beds,
        icu_beds=s.icu_beds,
        score=s.score,
        score_breakdown=s.score_breakdown,
        explanation=s.explanation,
        pros=s.pros,
        cons=s.cons,
        data_source=s.data_source,
        last_updated=s.last_updated,
        hospital_lat=s.hospital_lat,
        hospital_lng=s.hospital_lng,
        address=s.address,
        eta_minutes=s.eta_minutes,
    )


def _get_partial_match_suggestions(
    hospital_dicts: list[dict],
    required_equipment: list[str],
    ambulance_lat: float,
    ambulance_lng: float,
    limit: int = 3,
) -> list[str]:
    """
    For no-match situations, suggest the closest hospitals regardless
    of equipment filter so dispatchers have a manual fallback.
    """
    with_distance = []
    for h in hospital_dicts:
        lat = float(h.get("lat", h.get("latitude", 0)))
        lng = float(h.get("lng", h.get("longitude", 0)))
        dist = calculate_distance(ambulance_lat, ambulance_lng, lat, lng)
        with_distance.append((dist, h))

    with_distance.sort(key=lambda x: x[0])
    suggestions: list[str] = []
    for dist, h in with_distance[:limit]:
        h_equip = {e.lower() for e in (h.get("equipment") or [])}
        req_lower = [e.lower() for e in required_equipment]
        missing = [e for e in req_lower if e not in h_equip]
        missing_str = f" (missing: {', '.join(missing)})" if missing else ""
        suggestions.append(
            f"{h.get('name', 'Unknown')} — {dist:.1f} km away{missing_str}"
        )
    return suggestions


def _build_no_match_reason(rejection: dict, required_equipment: list[str]) -> str:
    parts: list[str] = []
    if rejection.get("missing_equipment", 0):
        n = rejection["missing_equipment"]
        parts.append(
            f"{n} hospital{'s' if n > 1 else ''} lacked required equipment "
            f"({', '.join(required_equipment) if required_equipment else 'unspecified'})"
        )
    if rejection.get("insufficient_beds", 0):
        n = rejection["insufficient_beds"]
        parts.append(f"{n} had insufficient bed capacity")
    if rejection.get("too_far", 0):
        n = rejection["too_far"]
        parts.append(f"{n} were beyond the safe transport radius")
    return (
        "No eligible hospitals found: " + "; ".join(parts) + "."
        if parts
        else "No hospitals matched the dispatch criteria."
    )


# ── Endpoint ────────────────────────────────────────────────────────────────

@router.post("/", response_model=DispatchResponse)
async def dispatch_ambulance(
    request: DispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ambulance":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts can dispatch"
        )

    try:
        # 1. Fetch all hospitals via optimized JOIN query
        loop = asyncio.get_running_loop()

        def fetch_hospitals():
            return db.execute(text("""
                SELECT
                    h.id, h.name, h.address, h.lat, h.lng,
                    NULL as speciality,
                    a.beds, a.icu, a.doctors, a.equipment, a.accepting,
                    a.updated_at, a.specialists
                FROM hospitals h
                JOIN availabilities a ON a.hospital_id = h.id
                WHERE a.updated_at = (
                    SELECT MAX(a2.updated_at)
                    FROM availabilities a2
                    WHERE a2.hospital_id = h.id
                )
            """)).fetchall()

        rows = await loop.run_in_executor(None, fetch_hospitals)

        hospital_dicts = []
        for r in rows:
            eq_raw = r[9]
            if isinstance(eq_raw, list):
                equipment = [e.lower() for e in eq_raw if e]
            elif isinstance(eq_raw, str):
                equipment = [e.strip().lower() for e in eq_raw.strip("{}").split(",") if e.strip()]
            else:
                equipment = []

            # Parse specialists
            spec_raw = r[12]
            if isinstance(spec_raw, str):
                try:
                    spec_raw = json.loads(spec_raw)
                except Exception:
                    spec_raw = {}
            if not isinstance(spec_raw, dict):
                spec_raw = {}

            hospital_dicts.append({
                "id":             r[0],
                "name":           r[1],
                "address":        r[2],
                "latitude":       float(r[3]),
                "longitude":      float(r[4]),
                "available_beds": r[6] or 0,
                "icu_beds":       r[7] or 0,
                "equipment":      equipment,
                "specialists":    spec_raw,
                "data_source":    "live",
                "last_updated":   r[11].isoformat() if r[11] else None,
            })

        if not hospital_dicts:
            return DispatchResponse(
                no_match=True,
                no_match_reason="No hospitals with availability data in the system.",
                fallback_options=[],
                error="No hospitals available",
            )

        # 2. Resolve equipment list (frontend sends either field)
        equip = request.get_equipment()

        # 3. Score hospitals
        ranked, rejection_summary = score_hospitals(
            hospitals=hospital_dicts,
            condition=request.condition,
            required_equipment=equip,
            ambulance_lat=request.ambulance_lat,
            ambulance_lng=request.ambulance_lng,
            severity_override=request.severity,
            top_n=3,
            db=db,
        )

        rejection_model = RejectionSummary(**rejection_summary)

        # Resolve severity for triage block
        condition_clean = request.condition.lower().replace("_", " ")
        severity_str = request.severity or SEVERITY_MAP.get(
            condition_clean, "moderate"
        )
        if hasattr(severity_str, "value"):
            severity_str = severity_str.value

        # 4. No-match path
        if not ranked:
            fallback = _get_partial_match_suggestions(
                hospital_dicts, equip,
                request.ambulance_lat, request.ambulance_lng,
            )
            reason = _build_no_match_reason(rejection_summary, equip)
            return DispatchResponse(
                no_match=True,
                no_match_reason=reason,
                fallback_options=fallback,
                rejected_hospitals=rejection_model,
                triage={
                    "condition": request.condition,
                    "severity": severity_str,
                    "required_equipment": equip,
                },
            )

        # 5. Build enriched response
        best = ranked[0]
        best_response = _scored_to_response(best)
        alternatives = [_scored_to_response(h) for h in ranked[1:]]

        # ORS override for ETA/distance on best hospital
        if settings.ors_api_key and settings.ors_api_key != "dummy_ors_key":
            try:
                async with httpx.AsyncClient() as client:
                    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car"
                    params = {
                        "api_key": settings.ors_api_key,
                        "start": f"{request.ambulance_lng},{request.ambulance_lat}",
                        "end": f"{best.hospital_lng},{best.hospital_lat}",
                    }
                    resp = await client.get(ors_url, params=params, timeout=5.0)
                    if resp.status_code == 200:
                        data = resp.json()
                        eta_sec = data['features'][0]['properties']['summary']['duration']
                        dist_meters = data['features'][0]['properties']['summary']['distance']
                        best_response.eta_minutes = int(eta_sec / 60)
                        best_response.distance_km = round(dist_meters / 1000, 1)
            except Exception as e:
                logging.getLogger(__name__).warning(
                    "ORS ETA calc failed, using haversine: %s", e
                )

        # 6. Save case and decrement beds
        new_case = Case(
            user_id=current_user.id,
            condition=request.condition,
            custom_condition=getattr(request, "custom_condition", None),
            equipment_needed=equip,
            ambulance_lat=request.ambulance_lat,
            ambulance_lng=request.ambulance_lng,
            assigned_hospital_id=best.hospital_id,
            final_score=best.score,
            distance_km=best_response.distance_km,
            eta_minutes=best_response.eta_minutes,
            notes=getattr(request, "notes", None),
        )

        def save_case_and_decrement():
            # 1. Atomic deduction
            rows_updated = db.query(Availability).filter(
                Availability.hospital_id == best.hospital_id,
                Availability.beds > 0
            ).update(
                {
                    Availability.beds: Availability.beds - 1,
                    Availability.updated_at: datetime.now(timezone.utc)
                },
                synchronize_session=False
            )

            if rows_updated == 0:
                # Race condition lost
                db.rollback()
                raise HTTPException(status_code=409, detail="Hospital at capacity, retry dispatch")

            # 2. Assign case
            db.add(new_case)
            db.commit()
            db.refresh(new_case)

            # 3. Create initial case event
            initial_event = CaseEvent(
                case_id=new_case.id,
                status="dispatched",
                actor_id=current_user.id,
                actor_role=current_user.role,
                note="Case dispatched by system",
            )
            db.add(initial_event)
            db.commit()

        await loop.run_in_executor(None, save_case_and_decrement)

        return DispatchResponse(
            case_id=new_case.id,
            status="dispatched",
            triage={
                "condition": request.condition,
                "severity": severity_str,
                "required_equipment": equip,
            },
            selected_hospital=best_response,
            alternatives=alternatives,
            rejected_hospitals=rejection_model,
            no_match=False,

            # Legacy flat fields — derived from selected_hospital
            hospital_id=best.hospital_id,
            hospital_name=best.name,
            address=best.address,
            final_score=best.score,
            confidence=best.score,
            distance_km=best_response.distance_km,
            eta_minutes=best_response.eta_minutes,
            beds=best.available_beds,
            icu=best.icu_beds,
            equipment_matched=list(equip),
            equipment_missing=[],
            hospital_lat=best.hospital_lat,
            hospital_lng=best.hospital_lng,
            ml_reasoning=best.explanation,
        )

    except Exception as exc:
        logging.getLogger(__name__).error("Dispatch pipeline error: %s", exc, exc_info=True)
        return DispatchResponse(
            error=f"Dispatch pipeline error: {str(exc)}",
            no_match=True,
            no_match_reason="Internal error — please retry or escalate manually.",
        )
