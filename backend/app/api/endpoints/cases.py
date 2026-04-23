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
from app.engine.dispatch_engine import reevaluate_routing
from app.middleware.rate_limit import limiter, LIMIT_CASES
from app.services.notification_service import send_arrival_notifications
from app.services.webhook_service import enqueue_case_status_webhook, process_webhook_delivery

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

    # District breakdown — group hospitals by district column
    rows = db.query(
        Hospital.district.label("district"),
        func.sum(Availability.beds).label("beds"),
        func.sum(Availability.icu).label("icu"),
        func.count(Availability.id).label("hospitals"),
        func.sum(func.cast(Availability.accepting, Integer)).label("accepting"),
    ).join(
        Hospital, Availability.hospital_id == Hospital.id
    ).group_by(
        Hospital.district
    ).all()

    districts = []
    for row in rows:
        districts.append({
            "name": row.district or "Unknown",
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
        actual_eta_minutes=update_data.actual_eta_minutes,
    )
    db.add(event)

    webhook_delivery_id: int | None = None
    try:
        webhook_delivery_id = enqueue_case_status_webhook(
            case=case,
            status=new_status,
            actor_role=current_user.role,
            note=update_data.note,
            db=db,
        )
    except Exception as exc:
        # Keep status transition non-blocking while migrations roll out.
        logger.warning("Webhook enqueue skipped for case %s: %s", case.id, exc)

    db.commit()

    if webhook_delivery_id is not None:
        try:
            asyncio.create_task(process_webhook_delivery(webhook_delivery_id))
        except RuntimeError:
            logger.warning("Webhook background delivery could not be scheduled for case %s", case.id)

    if new_status == "arrived":
        # Notify hospital staff with push + DLQ fallback handling.
        hospital_users = db.query(User).filter(
            User.hospital_id == case.assigned_hospital_id,
            User.fcm_token.is_not(None)
        ).all()
        await send_arrival_notifications(db=db, case=case, hospital_users=hospital_users)

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
