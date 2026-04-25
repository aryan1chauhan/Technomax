"""Webhook delivery tracking and retry logic for case lifecycle events."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Case, WebhookDelivery

logger = logging.getLogger(__name__)


def _payload_for_case_status(case: Case, status: str, actor_role: str | None, note: str | None) -> dict[str, Any]:
    return {
        "event_type": "case.status.updated",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "case": {
            "id": int(case.id),
            "status": status,
            "condition": case.condition,
            "assigned_hospital_id": case.assigned_hospital_id,
            "eta_minutes": case.eta_minutes,
            "final_score": case.final_score,
        },
        "meta": {
            "actor_role": actor_role,
            "note": note,
        },
    }


def _sign_payload(payload: dict[str, Any], secret: str) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), encoded, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def enqueue_case_status_webhook(
    *,
    case: Case,
    status: str,
    actor_role: str | None,
    note: str | None,
    db,
) -> int | None:
    target_url = settings.webhook_delivery_url
    if not target_url:
        return None

    payload = _payload_for_case_status(case, status, actor_role, note)
    signature = _sign_payload(payload, settings.webhook_secret)
    delivery = WebhookDelivery(
        case_id=int(case.id),
        event_type="case.status.updated",
        target_url=target_url,
        payload=payload,
        signature=signature,
        status="pending",
        attempt_count=0,
        max_attempts=max(int(settings.webhook_max_attempts), 1),
        next_attempt_at=datetime.now(timezone.utc),
    )
    db.add(delivery)
    db.flush()
    return int(delivery.id)


async def process_webhook_delivery(delivery_id: int) -> None:
    """Attempt webhook delivery with retry/backoff until success or max attempts."""
    while True:
        session = SessionLocal()
        sleep_seconds = 0.0
        should_continue = False
        try:
            delivery = session.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            if delivery is None:
                return

            if delivery.status == "succeeded":
                return

            now = datetime.now(timezone.utc)
            if delivery.next_attempt_at and delivery.next_attempt_at > now:
                sleep_seconds = (delivery.next_attempt_at - now).total_seconds()
                should_continue = True
            else:
                headers = {
                    "Content-Type": "application/json",
                    "X-MediRoute-Event": delivery.event_type,
                    "X-MediRoute-Delivery-Id": str(delivery.id),
                    "X-MediRoute-Signature": delivery.signature or "",
                }

                delivery.attempt_count = int(delivery.attempt_count or 0) + 1
                delivery.last_attempt_at = now

                try:
                    timeout = max(float(settings.webhook_timeout_seconds), 1.0)
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        response = await client.post(delivery.target_url, json=delivery.payload, headers=headers)

                    delivery.last_status_code = int(response.status_code)
                    body_snippet = response.text[:2000] if response.text else ""
                    delivery.response_body = {
                        "text": body_snippet,
                        "content_type": response.headers.get("content-type", ""),
                    }

                    if 200 <= response.status_code < 300:
                        delivery.status = "succeeded"
                        delivery.last_error = None
                        session.commit()
                        return

                    delivery.last_error = f"HTTP {response.status_code}"
                except (httpx.HTTPError, OSError, RuntimeError, ValueError, TypeError) as exc:
                    delivery.last_error = str(exc)[:1000]
                    delivery.last_status_code = None

                max_attempts = max(int(delivery.max_attempts or settings.webhook_max_attempts), 1)
                if int(delivery.attempt_count or 0) >= max_attempts:
                    delivery.status = "failed"
                    session.commit()
                    return

                backoff_base = max(float(settings.webhook_base_backoff_seconds), 0.1)
                attempt_index = max(int(delivery.attempt_count or 1) - 1, 0)
                backoff_seconds = min(backoff_base * (2 ** attempt_index), 30.0)
                delivery.next_attempt_at = now + timedelta(seconds=backoff_seconds)
                delivery.status = "pending"
                session.commit()
                sleep_seconds = backoff_seconds
                should_continue = True
        except Exception as exc:  # pragma: no cover - defensive safety path
            session.rollback()
            logger.warning("Webhook delivery loop failed for %s: %s", delivery_id, exc)
            return
        finally:
            session.close()

        if not should_continue:
            return
        await asyncio.sleep(max(sleep_seconds, 0.05))
