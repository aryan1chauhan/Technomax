import asyncio
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.transitions import BED_RESTORE_STATUSES, VALID_TRANSITIONS, validate_transition
from app.db.database import SessionLocal
from app.db.models import Availability, Case, CaseEvent, User
from app.engine.dispatch_engine import reevaluate_routing
from app.schemas.case import CaseStatusUpdate
from app.services.notification_service import send_arrival_notifications, send_decline_admin_notifications
from app.services.webhook_service import enqueue_case_status_webhook, process_webhook_delivery

logger = logging.getLogger(__name__)


async def trigger_reevaluation(case_id: int, vitals: dict | None, severity_score: int | None) -> None:
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


def authorize_case_status_update(case: Case, current_user: User) -> None:
    if current_user.role == "ambulance":
        if case.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to update this case")
    elif current_user.role == "hospital":
        # For universal hospital dashboard: allow any hospital to update status
        pass
    elif current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Invalid role")


async def apply_case_status_update(
    *,
    db: Session,
    case_id: int,
    update_data: CaseStatusUpdate,
    current_user: User,
) -> dict:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    authorize_case_status_update(case, current_user)

    new_status = update_data.status
    if not validate_transition(case.status, new_status):
        allowed = VALID_TRANSITIONS.get(case.status, [])
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition: {case.status} → {new_status}. Allowed: {allowed}",
        )

    if new_status == "arrived" and current_user.role != "ambulance":
        raise HTTPException(
            status_code=403,
            detail="Only ambulances can mark case as arrived",
        )
    if new_status in {"accepted", "declined"} and current_user.role != "hospital":
        raise HTTPException(
            status_code=403,
            detail="Only assigned hospitals can accept or decline cases",
        )
    if new_status == "declined" and not (update_data.note or "").strip():
        raise HTTPException(status_code=400, detail="Decline reason is required")

    # For universal hospital dashboard: handle reassignment and bed capacities dynamically
    old_hospital_id = case.assigned_hospital_id
    new_hospital_id = current_user.hospital_id if current_user.role == "hospital" else None
    
    reassigned = False
    if new_hospital_id and old_hospital_id and old_hospital_id != new_hospital_id:
        reassigned = True
        # Restore bed at old hospital (since they no longer have this case)
        db.query(Availability).filter(
            Availability.hospital_id == old_hospital_id
        ).update(
            {
                Availability.beds: Availability.beds + 1,
                Availability.updated_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
        
        # If the new hospital accepts, decrement bed at the new hospital
        if new_status == "accepted":
            db.query(Availability).filter(
                Availability.hospital_id == new_hospital_id
            ).update(
                {
                    Availability.beds: Availability.beds - 1,
                    Availability.updated_at: datetime.now(timezone.utc),
                },
                synchronize_session=False,
            )
            
        case.assigned_hospital_id = new_hospital_id

    case.status = new_status

    if not reassigned and case.assigned_hospital_id and new_status in BED_RESTORE_STATUSES:
        db.query(Availability).filter(
            Availability.hospital_id == case.assigned_hospital_id
        ).update(
            {
                Availability.beds: Availability.beds + 1,
                Availability.updated_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
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
        logger.warning("Webhook enqueue skipped for case %s: %s", case.id, exc)

    db.commit()

    if webhook_delivery_id is not None:
        try:
            asyncio.create_task(process_webhook_delivery(webhook_delivery_id))
        except RuntimeError:
            logger.warning("Webhook background delivery could not be scheduled for case %s", case.id)

    if new_status == "arrived":
        hospital_users = db.query(User).filter(
            User.hospital_id == case.assigned_hospital_id,
            User.fcm_token.is_not(None),
        ).all()
        await send_arrival_notifications(db=db, case=case, hospital_users=hospital_users)
    elif new_status == "declined":
        admin_users = db.query(User).filter(User.role == "admin").all()
        await send_decline_admin_notifications(
            db=db,
            case=case,
            admin_users=admin_users,
            reason=update_data.note or "No reason provided",
        )

    response_payload = {"status": new_status, "case_id": case.id}
    if new_status == "stabilized":
        try:
            asyncio.create_task(
                trigger_reevaluation(
                    case_id=case.id,
                    vitals=update_data.vitals,
                    severity_score=update_data.severity_score,
                )
            )
        except RuntimeError:
            response_payload["reroute_warning"] = "Secondary routing could not be scheduled. Please retry manually."

    return response_payload
