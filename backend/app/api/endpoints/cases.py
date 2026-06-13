from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc, Integer
from app.db.database import get_db
from app.db.models import Case, User, Hospital, Availability, CaseMessage
from app.schemas.dispatch import CaseOut
from app.schemas.case import CaseDeclineRequest, CaseStatusUpdate, CaseEventOut, CaseMessageCreate, CaseMessageOut, CaseMessagePage, CaseOverrideRequest
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
    # For universal hospital dashboard: allow any hospital account
    # if case.assigned_hospital_id != current_user.hospital_id:
    #     raise HTTPException(status_code=403, detail="Not authorized for this case")
    return case


def _require_case_participant(case: Case | None, current_user: User) -> Case:
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if current_user.role == "ambulance" and case.user_id == current_user.id:
        return case
    if current_user.role == "hospital":
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
    
    # Universal Hospital Dashboard: return all cases from the last 24 hours
    cases = db.query(Case)\
        .filter(Case.created_at >= since)\
        .order_by(Case.created_at.desc())\
        .all()
    
    results = []
    for c in cases:
        hosp_name = "None"
        if c.assigned_hospital_id:
            hosp = db.query(Hospital).filter(Hospital.id == c.assigned_hospital_id).first()
            if hosp:
                hosp_name = hosp.name
        results.append({
            "id": c.id,
            "user_id": c.user_id,
            "condition": c.condition,
            "custom_condition": c.custom_condition,
            "equipment_needed": c.equipment_needed or [],
            "ambulance_lat": c.ambulance_lat,
            "ambulance_lng": c.ambulance_lng,
            "assigned_hospital_id": c.assigned_hospital_id,
            "assigned_hospital_name": hosp_name,
            "final_score": c.final_score,
            "distance_km": c.distance_km,
            "eta_minutes": c.eta_minutes,
            "severity_score": getattr(c, "severity_score", None),
            "notes": c.notes,
            "status": c.status,
            "created_at": c.created_at,
        })
    
    return results


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


@router.put("/{case_id}/override-hospital")
@limiter.limit(LIMIT_CASES)
async def override_case_hospital(
    request: Request,  # noqa: ARG001
    case_id: int,
    override_data: CaseOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = request
    if current_user.role not in {"ambulance", "admin"}:
        raise HTTPException(
            status_code=403,
            detail="Only ambulance accounts or admins can override routing"
        )

    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.status not in {"dispatched", "declined"}:
        raise HTTPException(
            status_code=400,
            detail="Cannot override hospital once case is accepted or in transit"
        )

    old_hospital_id = case.assigned_hospital_id
    new_hospital_id = override_data.new_hospital_id

    if old_hospital_id == new_hospital_id:
        return {"status": "success", "detail": "Hospital unchanged"}

    # Verify new hospital exists
    new_hosp = db.query(Hospital).filter(Hospital.id == new_hospital_id).first()
    if not new_hosp:
        raise HTTPException(status_code=404, detail="New hospital not found")

    # Allocate bed at new hospital
    new_avail = db.query(Availability).filter(Availability.hospital_id == new_hospital_id).first()
    if not new_avail:
        raise HTTPException(status_code=404, detail="New hospital availability not found")

    # Demo capacity resilience: Replenish if beds are 0
    import os
    if os.getenv("TESTING") != "true" and new_avail.beds <= 0:
        new_avail.beds = 10
        db.flush()

    if new_avail.beds > 0:
        new_avail.beds -= 1
        new_avail.updated_at = datetime.now(timezone.utc)

    # Restore bed at old hospital
    if old_hospital_id:
        old_avail = db.query(Availability).filter(Availability.hospital_id == old_hospital_id).first()
        if old_avail:
            old_avail.beds += 1
            old_avail.updated_at = datetime.now(timezone.utc)

    case.assigned_hospital_id = new_hospital_id
    if override_data.distance_km is not None:
        case.distance_km = override_data.distance_km
    if override_data.eta_minutes is not None:
        case.eta_minutes = override_data.eta_minutes
    if override_data.final_score is not None:
        case.final_score = override_data.final_score

    # Add timeline event
    event = CaseEvent(
        case_id=case.id,
        status=case.status,
        actor_id=current_user.id,
        actor_role=current_user.role,
        note=f"Ambulance overrode routing to: {new_hosp.name}",
    )
    db.add(event)
    db.commit()

    return {"status": "success", "assigned_hospital_id": new_hospital_id}

