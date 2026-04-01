from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.db.models import Case, User, Availability, CaseEvent
from datetime import datetime, timezone
from app.schemas.dispatch import DispatchRequest, DispatchResponse
from app.core.security import get_current_user
from app.engine.ml_scorer import predict_best_hospital

import asyncio
import httpx
import logging
from app.core.config import settings
from fastapi import APIRouter, Depends, HTTPException, status

router = APIRouter(prefix="/api/dispatch")


@router.post("/", response_model=DispatchResponse)
async def dispatch_ambulance(
    request: DispatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ambulance":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ambulance accounts can dispatch"
        )

    # FIX: Single JOIN query instead of 188 individual availability lookups.
    # Previously: db.query(Hospital) then loop with db.query(Availability) per hospital
    # = 1 + 188 = 189 DB round-trips per dispatch → slow.
    # Now: 1 query total, roughly 20-50x faster.
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
            -- Keep only the most recent availability row per hospital
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
        # Handle both list (SQLAlchemy array) and raw string formats
        if isinstance(eq_raw, list):
            equipment = [e.lower() for e in eq_raw if e]
        elif isinstance(eq_raw, str):
            equipment = [e.strip().lower() for e in eq_raw.strip("{}").split(",") if e.strip()]
        else:
            equipment = []

        hospital_dicts.append({
            "id":         r[0],
            "name":       r[1],
            "address":    r[2],
            "lat":        float(r[3]),
            "lng":        float(r[4]),
            "speciality": r[5] or "",
            "beds":       r[6] or 0,
            "icu":        r[7] or 0,
            "doctors":    r[8] or 0,
            "equipment":  equipment,
            "accepting":  bool(r[10]),
            "specialists": r[12] or {},
        })

    result = predict_best_hospital(
        hospitals=hospital_dicts,
        equipment_needed=request.equipment_needed,
        ambulance_lat=request.ambulance_lat,
        ambulance_lng=request.ambulance_lng,
        condition=request.condition,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No suitable hospital found. All hospitals may be at capacity."
        )

    # Phase 4 ORS Integration
    if not settings.ors_api_key or settings.ors_api_key == "dummy_ors_key":
        # TODO: Drop in real ORS api key for prod
        pass
    else:
        try:
            async with httpx.AsyncClient() as client:
                ors_url = "https://api.openrouteservice.org/v2/directions/driving-car"
                params = {
                    "api_key": settings.ors_api_key,
                    "start": f"{request.ambulance_lng},{request.ambulance_lat}",
                    "end": f"{result['lng']},{result['lat']}",
                }
                resp = await client.get(ors_url, params=params, timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    eta_sec = data['features'][0]['properties']['summary']['duration']
                    dist_meters = data['features'][0]['properties']['summary']['distance']
                    # Overwrite ML scorer's simple haversine bounds with precise ORS values
                    result['eta_minutes'] = int(eta_sec / 60)
                    result['distance_km'] = round(dist_meters / 1000, 1)
        except Exception as e:
            logging.getLogger(__name__).warning("ORS ETA calc failed, falling back to haversine: %s", e)

    new_case = Case(
        user_id=current_user.id,
        condition=request.condition,
        custom_condition=getattr(request, "custom_condition", None),
        equipment_needed=request.equipment_needed,
        ambulance_lat=request.ambulance_lat,
        ambulance_lng=request.ambulance_lng,
        assigned_hospital_id=result["id"],
        final_score=result["final_score"],
        distance_km=result["distance_km"],
        eta_minutes=result["eta_minutes"],
        notes=getattr(request, "notes", None),
    )

    def save_case_and_decrement():
        db.add(new_case)
        db.commit()
        db.refresh(new_case)

        # [A] DECREMENT BEDS
        availability = db.query(Availability).filter(
            Availability.hospital_id == result["id"]
        ).first()
        if availability and availability.beds > 0:
            availability.beds -= 1
            availability.updated_at = datetime.now(timezone.utc)

        # [B] CREATE INITIAL CaseEvent
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
        status=new_case.status,
        hospital_id=result["id"],
        hospital_name=result["name"],
        address=result["address"],
        final_score=result["final_score"],
        confidence=result.get("confidence", 0.0),
        distance_km=result["distance_km"],
        eta_minutes=result["eta_minutes"],
        beds=result["beds"],
        icu=result["icu"],
        equipment_matched=result["equipment_matched"],
        equipment_missing=result["equipment_missing"],
        hospital_lat=result["lat"],
        hospital_lng=result["lng"],
        ml_reasoning=result.get("ml_reasoning", []),
    )

