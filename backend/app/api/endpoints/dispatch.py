from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.db.models import Case, User
from app.schemas.dispatch import DispatchRequest, DispatchResponse
from app.core.security import get_current_user
from app.engine.ml_scorer import predict_best_hospital

router = APIRouter(prefix="/api/dispatch")


@router.post("/", response_model=DispatchResponse)
def dispatch_ambulance(
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
    rows = db.execute(text("""
        SELECT
            h.id, h.name, h.address, h.lat, h.lng,
            h.speciality,
            a.beds, a.icu, a.doctors, a.equipment, a.accepting,
            a.updated_at
        FROM hospitals h
        JOIN availabilities a ON a.hospital_id = h.id
        -- Keep only the most recent availability row per hospital
        WHERE a.updated_at = (
            SELECT MAX(a2.updated_at)
            FROM availabilities a2
            WHERE a2.hospital_id = h.id
        )
    """)).fetchall()

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

    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    reasoning_str = (
        "; ".join(result["ml_reasoning"])
        if isinstance(result.get("ml_reasoning"), list)
        else str(result.get("ml_reasoning", ""))
    )

    return DispatchResponse(
        case_id=new_case.id,
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
        reason=reasoning_str,
    )
