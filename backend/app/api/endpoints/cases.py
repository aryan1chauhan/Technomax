from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc, Integer
from app.db.database import get_db
from app.db.models import Case, User, Hospital, Availability, CaseMessage
from app.schemas.dispatch import CaseOut
from app.schemas.case import CaseDeclineRequest, CaseStatusUpdate, CaseEventOut, CaseMessageCreate, CaseMessageOut, CaseMessagePage
from app.core.security import get_current_user
from app.db.models import CaseEvent
from app.middleware.rate_limit import limiter, LIMIT_CASES
from app.services.case_status_service import apply_case_status_update
from app.services.case_realtime import case_realtime_manager

router = APIRouter(prefix="/api/cases")


def _require_assigned_hospital(case: Case | None, current_user: User) -> Case:
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if current_user.role != "hospital":
        raise HTTPException(status_code=403, detail="Not a hospital account")
    if case.assigned_hospital_id != current_user.hospital_id:
        raise HTTPException(status_code=403, detail="Not authorized for this case")
    return case


def _require_case_participant(case: Case | None, current_user: User) -> Case:
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if current_user.role == "ambulance" and case.user_id == current_user.id:
        return case
    if current_user.role == "hospital" and case.assigned_hospital_id == current_user.hospital_id:
        return case
    raise HTTPException(status_code=403, detail="Not authorized for this case")


def _serialize_case_message(message: CaseMessage, sender: User) -> CaseMessageOut:
    return CaseMessageOut(
        id=message.id,
        case_id=message.case_id,
        sender_id=message.sender_id,
        sender_role=sender.role,
        sender_email=sender.email,
        body=message.body,
        sent_at=message.sent_at,
    )

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
    # Keep all status mutations routed through case_status_service so HTTP and
    # WebSocket paths share one transition/bed-restoration/audit implementation.
    return await apply_case_status_update(
        db=db,
        case_id=case_id,
        update_data=update_data,
        current_user=current_user,
    )

@router.post("/{case_id}/accept")
@limiter.limit(LIMIT_CASES)
async def accept_case(
    request: Request,  # noqa: ARG001
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = request
    case = _require_assigned_hospital(db.query(Case).filter(Case.id == case_id).first(), current_user)
    return await apply_case_status_update(
        db=db,
        case_id=case.id,
        update_data=CaseStatusUpdate(status="accepted", note="Case accepted by hospital"),
        current_user=current_user,
    )

@router.post("/{case_id}/decline")
@limiter.limit(LIMIT_CASES)
async def decline_case(
    request: Request,  # noqa: ARG001
    case_id: int,
    decline_data: CaseDeclineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = request
    case = _require_assigned_hospital(db.query(Case).filter(Case.id == case_id).first(), current_user)
    return await apply_case_status_update(
        db=db,
        case_id=case.id,
        update_data=CaseStatusUpdate(status="declined", note=decline_data.reason.strip()),
        current_user=current_user,
    )

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
    _require_case_participant(case, current_user)
            
    events = db.query(CaseEvent).filter(CaseEvent.case_id == case_id).order_by(CaseEvent.timestamp.asc()).all()
    return events


@router.get("/{case_id}/messages", response_model=CaseMessagePage)
@limiter.limit(LIMIT_CASES)
def get_case_messages(
    request: Request,  # noqa: ARG001
    case_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = request
    case = db.query(Case).filter(Case.id == case_id).first()
    _require_case_participant(case, current_user)

    total = db.query(CaseMessage).filter(CaseMessage.case_id == case_id).count()
    rows = (
        db.query(CaseMessage, User)
        .join(User, User.id == CaseMessage.sender_id)
        .filter(CaseMessage.case_id == case_id)
        .order_by(CaseMessage.sent_at.asc(), CaseMessage.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return CaseMessagePage(
        items=[_serialize_case_message(message, sender) for message, sender in rows],
        page=page,
        limit=limit,
        total=total,
    )


@router.post("/{case_id}/messages", response_model=CaseMessageOut, status_code=201)
@limiter.limit(LIMIT_CASES)
async def post_case_message(
    request: Request,  # noqa: ARG001
    case_id: int,
    payload: CaseMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = request
    case = db.query(Case).filter(Case.id == case_id).first()
    _require_case_participant(case, current_user)
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Message body cannot be empty")

    message = CaseMessage(
        case_id=case_id,
        sender_id=current_user.id,
        body=body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    serialized = _serialize_case_message(message, current_user)
    await case_realtime_manager.broadcast(case_id, {
        "type": "chat",
        "case_id": case_id,
        "message": serialized.model_dump(mode="json"),
    })
    return serialized
