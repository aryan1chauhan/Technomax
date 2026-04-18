import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc, Integer
from app.db.database import SessionLocal, get_db
from app.db.models import Case, User, Hospital, Availability
from app.schemas.dispatch import CaseOut
from app.schemas.case import CaseStatusUpdate, CaseEventOut
from app.core.security import get_current_user
from app.db.models import CaseEvent
from app.core.transitions import validate_transition, VALID_TRANSITIONS, BED_RESTORE_STATUSES
from app.core.firebase import send_push
from app.engine.dispatch_engine import reevaluate_routing
from app.middleware.rate_limit import limiter, LIMIT_CASES

router = APIRouter(prefix="/api/cases")
logger = logging.getLogger(__name__)


async def _trigger_reevaluation(case_id: int, vitals: dict | None, severity_score: int | None) -> None:
    db = SessionLocal()
    try:
        await reevaluate_routing(
            db=db,
            case_id=case_id,
            updated_vitals=vitals,
            updated_severity_score=severity_score,
        )
    except (ValueError, RuntimeError, KeyError, TypeError, OSError) as exc:
        logger.warning("Secondary reevaluation failed for case %s: %s", case_id, exc)
    finally:
        db.close()

@router.get("/", response_model=list[CaseOut])
@limiter.limit(LIMIT_CASES)
def get_cases(
    request: Request,  # noqa: ARG001
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ = request
    cases = db.query(Case)\
        .filter(Case.user_id == current_user.id)\
        .order_by(Case.created_at.desc())\
        .all()
        
    return cases

@router.get("/hospital")
@limiter.limit(LIMIT_CASES)
def get_hospital_cases(
    request: Request,  # noqa: ARG001
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ = request
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
@limiter.limit(LIMIT_CASES)
def admin_stats(
    request: Request,  # noqa: ARG001
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ = request
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

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

@router.put("/{case_id}/status")
@limiter.limit(LIMIT_CASES)
async def update_case_status(
    request: Request,  # noqa: ARG001
    case_id: int,
    update_data: CaseStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ = request
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role == "ambulance":
        if case.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this case")
    elif current_user.role == "hospital":
        if case.assigned_hospital_id != current_user.hospital_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this case")
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Invalid role")

    new_status = update_data.status
    if not validate_transition(case.status, new_status):
        allowed = VALID_TRANSITIONS.get(case.status, [])
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {case.status} → {new_status}. Allowed: {allowed}"
        )

    if new_status == "arrived" and current_user.role != "ambulance":
        raise HTTPException(
            status_code=403,
            detail="Only ambulances can mark case as arrived"
        )

    case.status = new_status

    if case.assigned_hospital_id and new_status in BED_RESTORE_STATUSES:
        db.query(Availability).filter(
            Availability.hospital_id == case.assigned_hospital_id
        ).update(
            {
                Availability.beds: Availability.beds + 1,
                Availability.updated_at: datetime.now(timezone.utc)
            },
            synchronize_session=False
        )

    event = CaseEvent(
        case_id=case.id,
        status=new_status,
        actor_id=current_user.id,
        actor_role=current_user.role,
        note=update_data.note,
    )
    db.add(event)
    db.commit()

    if new_status == "arrived":
        # Notify hospital staff via FCM
        hospital_users = db.query(User).filter(
            User.hospital_id == case.assigned_hospital_id,
            User.fcm_token.is_not(None)
        ).all()
        for user in hospital_users:
            send_push(
                token=user.fcm_token,
                title="Ambulance Arrived",
                body=f"Ambulance for case #{case.id} has arrived at your hospital.",
                data={"case_id": str(case.id), "status": "arrived"}
            )

    response_payload = {"status": new_status, "case_id": case.id}
    if new_status == "stabilized":
        try:
            asyncio.create_task(
                _trigger_reevaluation(
                    case_id=case.id,
                    vitals=update_data.vitals,
                    severity_score=update_data.severity_score,
                )
            )
        except RuntimeError:
            response_payload["reroute_warning"] = "Secondary routing could not be scheduled. Please retry manually."
    
    return response_payload

@router.get("/{case_id}/timeline", response_model=list[CaseEventOut])
@limiter.limit(LIMIT_CASES)
def get_case_timeline(
    request: Request,  # noqa: ARG001
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _ = request
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if current_user.role == "ambulance":
        if case.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this case")
    elif current_user.role == "hospital":
        if case.assigned_hospital_id != current_user.hospital_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this case")
            
    events = db.query(CaseEvent).filter(CaseEvent.case_id == case_id).order_by(CaseEvent.timestamp.asc()).all()
    return events
