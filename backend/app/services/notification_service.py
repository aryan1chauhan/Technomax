"""Notification delivery with DLQ tracking and SMS fallback."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable

from app.core.config import settings
from app.core.firebase import send_push
from app.db.models import Case, NotificationDelivery, User

logger = logging.getLogger(__name__)


def _enqueue_delivery(
    *,
    db,
    case_id: int,
    user_id: int | None,
    channel: str,
    provider: str,
    target: str,
    payload: dict,
    max_attempts: int,
    is_dlq: bool,
    fallback_from_id: int | None = None,
) -> NotificationDelivery:
    delivery = NotificationDelivery(
        case_id=case_id,
        user_id=user_id,
        channel=channel,
        provider=provider,
        target=target,
        payload=payload,
        status="pending",
        attempt_count=0,
        max_attempts=max_attempts,
        is_dlq=is_dlq,
        fallback_from_id=fallback_from_id,
    )
    db.add(delivery)
    db.flush()
    return delivery


def _mark_delivery(
    *,
    db,
    delivery: NotificationDelivery,
    ok: bool,
    error: str | None,
) -> None:
    delivery.attempt_count = int(delivery.attempt_count or 0) + 1
    delivery.status = "succeeded" if ok else "failed"
    delivery.last_error = None if ok else (error or "unknown")
    db.commit()


async def _send_push_with_timeout(*, token: str, title: str, body: str, data: dict) -> tuple[bool, str | None]:
    try:
        timeout = max(float(settings.webhook_timeout_seconds), 1.0)
        ok = await asyncio.wait_for(
            asyncio.to_thread(send_push, token=token, title=title, body=body, data=data),
            timeout=timeout,
        )
        return bool(ok), None if ok else "push_failed"
    except asyncio.TimeoutError:
        return False, "push_timeout"
    except Exception as exc:  # pragma: no cover - defensive
        return False, str(exc)


async def _send_sms_with_timeout(*, target: str, message: str) -> tuple[bool, str | None]:
    # Placeholder implementation; external SMS provider wiring can replace this.
    if not target:
        return False, "sms_target_missing"

    try:
        timeout = max(float(settings.sms_timeout_seconds), 1.0)

        async def _send_stub() -> bool:
            logger.warning("SMS fallback triggered for %s: %s", target, message)
            return False

        ok = await asyncio.wait_for(_send_stub(), timeout=timeout)
        return bool(ok), None if ok else "sms_failed"
    except asyncio.TimeoutError:
        return False, "sms_timeout"
    except Exception as exc:  # pragma: no cover - defensive
        return False, str(exc)


def _case_condition_label(case: Case) -> str:
    return str(getattr(case, "custom_condition", None) or getattr(case, "condition", "") or "emergency").replace("_", " ")


async def _notify_users(
    *,
    db,
    case: Case,
    users: Iterable[User],
    title: str,
    body: str,
    payload: dict,
) -> None:
    user_list = list(users)
    # 1. Internal In-App Notifications (Fast)
    for user in user_list:
        try:
            in_app = _enqueue_delivery(
                db=db,
                case_id=int(case.id),
                user_id=int(user.id),
                channel="in_app",
                provider="database",
                target=f"user:{user.id}",
                payload=payload,
                max_attempts=1,
                is_dlq=False,
            )
            _mark_delivery(db=db, delivery=in_app, ok=True, error=None)
        except Exception as exc:
            db.rollback()
            logger.warning("In-app delivery tracking unavailable for case %s: %s", case.id, exc)

    # 2. Prepare Push Deliveries
    push_tasks = []
    deliveries_to_update = []

    for user in user_list:
        token = (user.fcm_token or "").strip()
        if not token:
            continue

        try:
            push_delivery = _enqueue_delivery(
                db=db,
                case_id=int(case.id),
                user_id=int(user.id),
                channel="push",
                provider="fcm",
                target=token,
                payload=payload,
                max_attempts=1,
                is_dlq=False,
            )
            db.commit()
            
            # We store the ID to re-fetch in a new session if needed, 
            # but here we'll try to update in the current session after the gather.
            deliveries_to_update.append(push_delivery)
            push_tasks.append(_send_push_with_timeout(
                token=token,
                title=title,
                body=body,
                data=payload,
            ))
        except Exception as exc:
            db.rollback()
            logger.warning("Push delivery tracking unavailable for case %s: %s", case.id, exc)

    if not push_tasks:
        return

    # 3. Parallel Push Sends (Slow I/O - happens while DB connection might be idle but still held)
    # Note: To fully release the connection, we would need to close 'db' here and re-open later.
    # For now, parallelizing reduces the duration significantly.
    results = await asyncio.gather(*push_tasks)

    # 4. Batch Update Results
    for delivery, (ok, error) in zip(deliveries_to_update, results):
        try:
            _mark_delivery(db=db, delivery=delivery, ok=ok, error=error)
        except Exception as exc:
            db.rollback()
            logger.warning("Push delivery status update failed for case %s: %s", case.id, exc)


async def send_dispatch_notifications(*, db, case: Case, hospital_users: Iterable[User]) -> None:
    title = "Incoming Emergency Case"
    body = f"Case #{case.id}: {_case_condition_label(case)} is awaiting hospital response."
    payload = {
        "case_id": str(case.id),
        "status": "dispatched",
        "type": "case_dispatched",
    }
    await _notify_users(db=db, case=case, users=hospital_users, title=title, body=body, payload=payload)


async def send_decline_admin_notifications(*, db, case: Case, admin_users: Iterable[User], reason: str) -> None:
    admins = list(admin_users)
    title = "Hospital Declined Case"
    body = f"Case #{case.id} was declined. Reason: {reason}"
    payload = {
        "case_id": str(case.id),
        "status": "declined",
        "type": "case_declined",
        "reason": reason,
    }

    if not admins:
        try:
            delivery = _enqueue_delivery(
                db=db,
                case_id=int(case.id),
                user_id=None,
                channel="in_app",
                provider="database",
                target="admin:broadcast",
                payload=payload,
                max_attempts=1,
                is_dlq=False,
            )
            _mark_delivery(db=db, delivery=delivery, ok=True, error=None)
        except Exception as exc:
            db.rollback()
            logger.warning("Admin decline notification unavailable for case %s: %s", case.id, exc)
        return

    await _notify_users(db=db, case=case, users=admins, title=title, body=body, payload=payload)


async def send_arrival_notifications(*, db, case: Case, hospital_users: Iterable[User]) -> None:
    title = "Ambulance Arrived"
    body = f"Ambulance for case #{case.id} has arrived at your hospital."

    for user in hospital_users:
        token = (user.fcm_token or "").strip()
        if not token:
            continue

        payload = {"case_id": str(case.id), "status": "arrived"}
        try:
            push_delivery = _enqueue_delivery(
                db=db,
                case_id=int(case.id),
                user_id=int(user.id),
                channel="push",
                provider="fcm",
                target=token,
                payload=payload,
                max_attempts=1,
                is_dlq=False,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("Push delivery tracking unavailable for case %s: %s", case.id, exc)
            push_delivery = None

        push_ok, push_error = await _send_push_with_timeout(token=token, title=title, body=body, data=payload)

        if push_delivery is not None:
            try:
                _mark_delivery(db=db, delivery=push_delivery, ok=push_ok, error=push_error)
            except Exception as exc:
                db.rollback()
                logger.warning("Push delivery status update failed for case %s: %s", case.id, exc)

        if push_ok:
            continue

        # DLQ + fallback path: timeout and explicit failures both trigger SMS fallback.
        sms_target = (settings.sms_fallback_number or "").strip()
        if not sms_target:
            continue

        try:
            sms_delivery = _enqueue_delivery(
                db=db,
                case_id=int(case.id),
                user_id=int(user.id),
                channel="sms",
                provider="fallback",
                target=sms_target,
                payload={"message": body, "case_id": str(case.id)},
                max_attempts=1,
                is_dlq=True,
                fallback_from_id=getattr(push_delivery, "id", None),
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("SMS fallback tracking unavailable for case %s: %s", case.id, exc)
            sms_delivery = None

        sms_ok, sms_error = await _send_sms_with_timeout(
            target=sms_target,
            message=f"[MediRoute] {body}",
        )

        if sms_delivery is not None:
            try:
                _mark_delivery(db=db, delivery=sms_delivery, ok=sms_ok, error=sms_error)
            except Exception as exc:
                db.rollback()
                logger.warning("SMS delivery status update failed for case %s: %s", case.id, exc)
