"""Audit worker for async queue consumption.

This worker runs on the slow path and must not affect FAST API latency.
"""

from __future__ import annotations

import json
import time
from typing import Any
import logging

from async_queue.redis_client import redis_client
from sqlalchemy.exc import SQLAlchemyError

from db.connection import SessionLocal, init_db
from db.models import AuditLog
from services.metrics_service import metrics
from workers.drift_worker import check_drift


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")

try:
    from redis.exceptions import RedisError as _RedisError
except ImportError:
    class _RedisError(Exception):
        pass


def process_audit(data: dict[str, Any]) -> None:
    """Process queued audit event and persist audit + observability data."""
    event = dict(data)
    output = event.get("output")
    payload = output if isinstance(output, dict) else event

    case_id = str(
        event.get("case_id")
        or payload.get("case_id")
        or payload.get("decision_id")
        or ""
    ).strip()

    score = (
        event.get("final_score")
        or event.get("score")
        or event.get("decision_score")
        or payload.get("final_score")
        or payload.get("score")
        or payload.get("decision_score")
        or (event.get("output") or {}).get("final_score")
        or (event.get("output") or {}).get("score")
        or (event.get("output") or {}).get("decision_score")
        or ((event.get("output") or {}).get("reasoning") or {}).get("ml_score")
        or (payload.get("reasoning") or {}).get("ml_score")
        or (((event.get("output") or {}).get("ranked_candidates") or [{}])[0].get("score"))
        or ((payload.get("ranked_candidates") or [{}])[0].get("score"))
        or 0
    )

    try:
        score_value = float(score)
    except (TypeError, ValueError):
        score_value = 0.0

    failure = payload.get("failure_type")
    failure_type = str(failure) if failure else None

    if case_id:
        session = SessionLocal()
        try:
            logger.info("WRITING TO DB %s", data.get("case_id"))
            log = AuditLog(
                case_id=case_id,
                input_payload=dict(event.get("input") or {}),
                output_payload=dict(event.get("output") or payload),
                score=score_value,
            )
            session.merge(log)
            session.commit()
            logger.info("COMMITTED")
        except Exception as e:
            session.rollback()
            logger.exception("DB ERROR while committing case %s: %s", case_id, e)
        finally:
            session.close()

    metrics.record(score=score_value, failure_type=failure_type)
    check_drift()


def run_worker() -> None:
    try:
        init_db()
    except (SQLAlchemyError, OSError, RuntimeError, ValueError, TypeError):
        # Keep worker alive even if DB init is temporarily unavailable.
        pass

    while True:
        try:
            item = redis_client.brpop("audit_queue")
            if item:
                data = json.loads(item[1])
                logger.info("WORKER RECEIVED %s", data.get("case_id"))
                process_audit(data)
        except (_RedisError, OSError, RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            # Worker resilience loop: keep process alive on transient failures.
            time.sleep(1)


if __name__ == "__main__":
    run_worker()
