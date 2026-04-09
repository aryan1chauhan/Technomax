"""
dispatch.py — Enriched dispatch endpoint.

Key changes from original:
- Calls score_hospitals() from new transparent scorer
- Returns ScoredHospitalResponse + alternatives + rejected_hospitals
- Keeps all legacy flat fields derived from selected_hospital
- Beds are decremented atomically; restored on cancel/complete (cases.py)
- Graceful no_match handling with fallback suggestions
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.db.database import get_db
from app.db.models import Case, User, Availability, CaseEvent, Hospital
from datetime import datetime, timezone
from app.schemas.dispatch import (
    DispatchRequest, DispatchResponse,
    ScoredHospitalResponse, RejectionSummary,
)
from app.core.security import get_current_user
from app.engine.ml_scorer import rank_hospitals, CONDITION_SEVERITY_MAP
from app.engine.haversine import calculate_distance
from app.middleware.rate_limit import limiter, LIMIT_DISPATCH

import asyncio
import json
import httpx
import logging
from app.core.config import settings


router = APIRouter(prefix="/api/dispatch")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _scored_to_response(d: dict) -> ScoredHospitalResponse:
    """Convert Scored dictionary → Pydantic response model."""
    detailed_breakdown = d.get("score_breakdown", {})
    compact_breakdown = {
        "distance": float(detailed_breakdown.get("distance_score", 0.0)),
        "beds": float(detailed_breakdown.get("bed_score", 0.0)),
        "specialist": 1.0 if detailed_breakdown.get("specialist_present") else 0.0,
        "equipment": float(detailed_breakdown.get("equipment_match", 0.0)),
        "outcome": float(d.get("score", 0.0)),
    }
    eta_minutes = d.get("eta_minutes")
    if eta_minutes is None:
        eta_minutes = max(1, int(round((detailed_breakdown.get("distance_km", 0) / 40.0) * 60)))

    explanation = d.get("explanation")
    if isinstance(explanation, str):
        explanation = [explanation]
    elif not isinstance(explanation, list):
        explanation = []

    return ScoredHospitalResponse(
        hospital_id=d["id"],
        name=d["name"],
        distance_km=d["score_breakdown"]["distance_km"],
        available_beds=d["available_beds"],
        icu_beds=d["icu_beds"],
        score=d["score"],
        score_breakdown=compact_breakdown,
        explanation=explanation,
        pros=d["pros"],
        cons=d["cons"],
        data_source=d.get("data_source", "live"),
        last_updated=d.get("last_updated"),
        hospital_lat=d["latitude"],
        hospital_lng=d["longitude"],
        address=d.get("address", ""),
        eta_minutes=eta_minutes,
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


def _build_rejection_summary(
    hospital_dicts: list[dict],
    ranked: list[dict],
    required_equipment: list[str],
) -> RejectionSummary:
    req = {e.lower() for e in required_equipment if e}
    missing_equipment = 0
    insufficient_beds = 0

    for h in hospital_dicts:
        h_equip = {e.lower() for e in (h.get("equipment") or [])}
        if req and not req.issubset(h_equip):
            missing_equipment += 1
        if (h.get("available_beds") or 0) <= 0:
            insufficient_beds += 1

    total_evaluated = len(hospital_dicts)
    total_passed = len(ranked)
    total_rejected = max(total_evaluated - total_passed, 0)

    return RejectionSummary(
        missing_equipment=missing_equipment,
        insufficient_beds=insufficient_beds,
        too_far=0,
        total_rejected=total_rejected,
        total_evaluated=total_evaluated,
        total_passed=total_passed,
    )


# ── Endpoint ────────────────────────────────────────────────────────────────

@router.post("/", response_model=DispatchResponse)
# IMPORTANT: slowapi requires limiter.limit to be BELOW the router decorator
@limiter.limit(LIMIT_DISPATCH)
async def dispatch_ambulance(
    request: Request,
    dispatch_request: DispatchRequest,
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
            latest_avail = db.query(
                Availability.hospital_id.label("hospital_id"),
                func.max(Availability.updated_at).label("max_updated"),
            ).group_by(Availability.hospital_id).subquery()

            return db.query(
                Hospital.id,
                Hospital.name,
                Hospital.address,
                Hospital.lat,
                Hospital.lng,
                Availability.beds,
                Availability.icu,
                Availability.doctors,
                Availability.equipment,
                Availability.accepting,
                Availability.updated_at,
                Availability.specialists,
            ).join(
                latest_avail,
                Hospital.id == latest_avail.c.hospital_id,
            ).join(
                Availability,
                and_(
                    Availability.hospital_id == latest_avail.c.hospital_id,
                    Availability.updated_at == latest_avail.c.max_updated,
                ),
            ).all()

        rows = await loop.run_in_executor(None, fetch_hospitals)

        hospital_dicts = []
        for r in rows:
            eq_raw = r[8]
            if isinstance(eq_raw, list):
                equipment = [e.lower() for e in eq_raw if e]
            elif isinstance(eq_raw, str):
                equipment = [e.strip().lower() for e in eq_raw.strip("{}").split(",") if e.strip()]
            else:
                equipment = []

            # Parse specialists
            spec_raw = r[11]
            if isinstance(spec_raw, str):
                try:
                    spec_raw = json.loads(spec_raw)
                except (TypeError, json.JSONDecodeError):
                    spec_raw = {}
            if not isinstance(spec_raw, dict):
                spec_raw = {}

            hospital_dicts.append({
                "id":             r[0],
                "name":           r[1],
                "address":        r[2],
                "latitude":       float(r[3]),
                "longitude":      float(r[4]),
                "available_beds": r[5] or 0,
                "icu_beds":       r[6] or 0,
                "equipment":      equipment,
                "accepting":      bool(r[9]),
                "specialists":    spec_raw,
                "specialist_count": len(spec_raw),
                "data_source":    "live",
                "last_updated":   r[10].isoformat() if r[10] else None,
            })

        if not hospital_dicts:
            return DispatchResponse(
                no_match=True,
                no_match_reason="No hospitals with availability data in the system.",
                fallback_options=[],
                error="No hospitals available",
            )

        # 2. Resolve equipment list (frontend sends either field)
        equip = dispatch_request.get_equipment()

        # 3. Score hospitals
        req_set = {e.lower() for e in equip}
        eligible_hospitals = []
        for h in hospital_dicts:
            if not h.get("accepting", True):
                continue
            if (h.get("available_beds") or 0) <= 0:
                continue
            h_equip = {e.lower() for e in (h.get("equipment") or [])}
            if req_set and not req_set.issubset(h_equip):
                continue
            eligible_hospitals.append(h)

        ranked = rank_hospitals(
            eligible_hospitals,
            ambulance_lat=dispatch_request.ambulance_lat,
            ambulance_lon=dispatch_request.ambulance_lng,
            required_equipment=equip,
            condition=dispatch_request.condition,
        )

        rejection_model = _build_rejection_summary(
            hospital_dicts=hospital_dicts,
            ranked=ranked,
            required_equipment=equip,
        )

        # Resolve severity for triage block
        if getattr(dispatch_request, "severity", None):
            severity_str = dispatch_request.severity
        else:
            severity_val = CONDITION_SEVERITY_MAP.get(dispatch_request.condition.lower(), 1)
            severity_str = "minor" if severity_val == 1 else "moderate" if severity_val == 2 else "critical"
            
        if hasattr(severity_str, "value"):
            severity_str = severity_str.value

        # 4. No-match path
        if not ranked:
            fallback = _get_partial_match_suggestions(
                hospital_dicts, equip,
                dispatch_request.ambulance_lat, dispatch_request.ambulance_lng,
            )
            reason = _build_no_match_reason(rejection_model.model_dump(), equip)
            return DispatchResponse(
                no_match=True,
                no_match_reason=reason,
                fallback_options=fallback,
                rejected_hospitals=rejection_model,
                triage={
                    "condition": dispatch_request.condition,
                    "severity": severity_str,
                    "required_equipment": equip,
                },
            )

        # 5. Build enriched response
        best = ranked[0]
        best_response = _scored_to_response(best)
        alternatives = [_scored_to_response(h) for h in ranked[1:4]]

        # ORS override for ETA/distance on best hospital
        if settings.ors_api_key and settings.ors_api_key != "dummy_ors_key":
            try:
                async with httpx.AsyncClient() as client:
                    ors_url = "https://api.openrouteservice.org/v2/directions/driving-car"
                    params = {
                        "api_key": settings.ors_api_key,
                        "start": f"{dispatch_request.ambulance_lng},{dispatch_request.ambulance_lat}",
                        "end": f"{best['longitude']},{best['latitude']}",
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
            condition=dispatch_request.condition,
            custom_condition=getattr(dispatch_request, "custom_condition", None),
            equipment_needed=equip,
            ambulance_lat=dispatch_request.ambulance_lat,
            ambulance_lng=dispatch_request.ambulance_lng,
            assigned_hospital_id=best["id"],
            final_score=best["score"],
            distance_km=best_response.distance_km,
            eta_minutes=best_response.eta_minutes,
            notes=getattr(dispatch_request, "notes", None),
        )

        def save_case_and_decrement():
            # 1. Atomic deduction
            rows_updated = db.query(Availability).filter(
                Availability.hospital_id == best["id"],
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
                "condition": dispatch_request.condition,
                "severity": severity_str,
                "required_equipment": equip,
            },
            selected_hospital=best_response,
            alternatives=alternatives,
            rejected_hospitals=rejection_model,
            no_match=False,

            # Legacy flat fields — derived from selected_hospital
            hospital_id=best["id"],
            hospital_name=best["name"],
            address=best.get("address", ""),
            final_score=best["score"],
            confidence=best["score"],
            distance_km=best_response.distance_km,
            eta_minutes=best_response.eta_minutes,
            beds=best["available_beds"],
            icu=best["icu_beds"],
            equipment_matched=list(equip),
            equipment_missing=[],
            hospital_lat=best["latitude"],
            hospital_lng=best["longitude"],
            ml_reasoning=best_response.explanation,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logging.getLogger(__name__).error("Dispatch pipeline error: %s", exc, exc_info=True)
        return DispatchResponse(
            error=f"Dispatch pipeline error: {str(exc)}",
            no_match=True,
            no_match_reason="Internal error — please retry or escalate manually.",
        )
