from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc, Integer
from app.db.database import get_db
from app.db.models import Case, User, Hospital, Availability
from app.schemas.dispatch import CaseOut
from app.core.security import get_current_user

router = APIRouter(prefix="/api/cases")

@router.get("/", response_model=list[CaseOut])
def get_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    cases = db.query(Case)\
        .filter(Case.user_id == current_user.id)\
        .order_by(Case.created_at.desc())\
        .all()
        
    return cases

@router.get("/hospital")
def get_hospital_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "hospital":
        raise HTTPException(status_code=403, detail="Not a hospital account")
    
    # Only show cases from last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    
    cases = db.query(Case)\
        .filter(Case.assigned_hospital_id == current_user.hospital_id)\
        .filter(Case.created_at >= since)\
        .order_by(Case.created_at.desc())\
        .all()
    
    return cases

@router.get("/admin/stats")
def admin_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("admin", "ambulance", "hospital"):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Total hospitals + accepting count
    total_hospitals = db.query(Hospital).count()
    accepting = db.query(Availability).filter(Availability.accepting == True).count()

    # Aggregate bed/ICU counts
    agg = db.query(
        func.sum(Availability.beds).label("total_beds"),
        func.sum(Availability.icu).label("total_icu"),
    ).first()

    # Cases in last 24h
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_cases = (
        db.query(Case, Hospital)
        .join(Hospital, Case.assigned_hospital_id == Hospital.id)
        .filter(Case.created_at >= since)
        .order_by(desc(Case.created_at))
        .limit(15)
        .all()
    )

    # Total cases all time
    total_cases = db.query(Case).count()

    # District breakdown — group hospitals by lat ranges
    # (approximate district mapping using hospital IDs)
    district_map = [
        {"name": "Dehradun",   "id_min": 93,  "id_max": 132},
        {"name": "Rishikesh",  "id_min": 133, "id_max": 157},
        {"name": "Haridwar",   "id_min": 66,  "id_max": 92},
        {"name": "Roorkee",    "id_min": 25,  "id_max": 65},
        {"name": "Haldwani",   "id_min": 158, "id_max": 187},
        {"name": "Nainital",   "id_min": 188, "id_max": 212},
    ]

    districts = []
    for d in district_map:
        row = db.query(
            func.sum(Availability.beds).label("beds"),
            func.sum(Availability.icu).label("icu"),
            func.count(Availability.id).label("hospitals"),
            func.sum(func.cast(Availability.accepting, Integer)).label("accepting"),
        ).join(Hospital, Availability.hospital_id == Hospital.id
        ).filter(
            Hospital.id >= d["id_min"],
            Hospital.id <= d["id_max"]
        ).first()

        districts.append({
            "name": d["name"],
            "hospitals": row.hospitals or 0,
            "beds": row.beds or 0,
            "icu": row.icu or 0,
            "accepting": row.accepting or 0,
        })

    cases_out = []
    for case, hosp in recent_cases:
        cases_out.append({
            "id": case.id,
            "condition": case.condition,
            "hospital_name": hosp.name,
            "score": round(case.final_score or 0, 3),
            "distance_km": round(case.distance_km or 0, 1),
            "eta_minutes": case.eta_minutes,
            "created_at": case.created_at.strftime("%H:%M:%S"),
        })

    return {
        "total_hospitals": total_hospitals,
        "accepting_hospitals": accepting,
        "total_beds": int(agg.total_beds or 0),
        "total_icu": int(agg.total_icu or 0),
        "total_cases": total_cases,
        "cases_last_24h": len(cases_out),
        "recent_cases": cases_out,
        "districts": districts,
    }
