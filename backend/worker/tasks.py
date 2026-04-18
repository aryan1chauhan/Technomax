"""
MediRoute — RQ Worker Tasks
Fixed version: explicit DATABASE_URL validation, connection target logging,
rollback-safe commit, and a startup self-test so misconfiguration fails loud.
"""

import os
import json
import uuid
import logging
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [worker] %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ── Validate env at import time so misconfiguration surfaces immediately ──────
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/mediroute"
    log.warning(
        "DATABASE_URL not set in environment — falling back to default: %s\n"
        "  If your Postgres is in Docker, this may be the wrong host/port!\n"
        "  Set DATABASE_URL explicitly before starting the worker.",
        DATABASE_URL,
    )
else:
    log.info("DATABASE_URL loaded from environment: %s", DATABASE_URL)


def _get_conn(autocommit: bool = False):
    """
    Open a psycopg2 connection and log the actual host/port/db we landed on.
    autocommit must be set BEFORE any query fires, so we do it here.
    """
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = autocommit         # set before first query — safe here
    cur  = conn.cursor()
    cur.execute(
        "SELECT current_database(), inet_server_addr(), inet_server_port()"
    )
    row = cur.fetchone()
    log.info(
        "DB connection: db=%s  host=%s  port=%s  autocommit=%s",
        row["current_database"],
        row["inet_server_addr"],
        row["inet_server_port"],
        autocommit,
    )
    if not autocommit:
        conn.rollback()                  # discard the implicit txn from the SELECT above
    return conn


def audit_log(payload: dict) -> dict:
    """
    RQ task — persist one dispatch decision to audit_logs.

    payload keys:
        case_id, condition_type, severity_score,
        ambulance_lat, ambulance_lng,
        selected_hospital_id, selected_hospital_name,
        score, score_breakdown, vitals,
        required_equipment, ambulance_equipment, all_hospitals
    """
    case_id = payload.get("case_id", str(uuid.uuid4()))
    log.info("audit_log task started | case_id=%s", case_id)

    conn = None
    try:
        conn = _get_conn(autocommit=False)   # explicit txn — set before any query fires

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    case_id, condition_type, severity_score,
                    ambulance_lat, ambulance_lng,
                    selected_hospital_id, selected_hospital_name,
                    score, score_breakdown, vitals,
                    required_equipment, ambulance_equipment, all_hospitals
                ) VALUES (
                    %(case_id)s, %(condition_type)s, %(severity_score)s,
                    %(ambulance_lat)s, %(ambulance_lng)s,
                    %(selected_hospital_id)s, %(selected_hospital_name)s,
                    %(score)s,
                    %(score_breakdown)s::jsonb,
                    %(vitals)s::jsonb,
                    %(required_equipment)s,
                    %(ambulance_equipment)s,
                    %(all_hospitals)s::jsonb
                )
                RETURNING id
                """,
                {
                    "case_id":               case_id,
                    "condition_type":        payload.get("condition_type"),
                    "severity_score":        payload.get("severity_score"),
                    "ambulance_lat":         payload.get("ambulance_lat"),
                    "ambulance_lng":         payload.get("ambulance_lng"),
                    "selected_hospital_id":  payload.get("selected_hospital_id", 0),
                    "selected_hospital_name":payload.get("selected_hospital_name", ""),
                    "score":                 payload.get("score", 0.0),
                    "score_breakdown":       json.dumps(payload.get("score_breakdown", {})),
                    "vitals":                json.dumps(payload.get("vitals", {})),
                    "required_equipment":    payload.get("required_equipment", []),
                    "ambulance_equipment":   payload.get("ambulance_equipment", []),
                    "all_hospitals":         json.dumps(payload.get("all_hospitals", [])),
                },
            )
            row_id = cur.fetchone()["id"]

        conn.commit()
        log.info("COMMITTED | case_id=%s → audit_logs.id=%d", case_id, row_id)
        return {"status": "ok", "audit_id": row_id, "case_id": case_id}

    except Exception as exc:
        if conn:
            conn.rollback()
            log.error("ROLLED BACK | case_id=%s | error=%s", case_id, exc)
        raise   # re-raise so RQ marks the job as failed (visible in rq info)

    finally:
        if conn:
            conn.close()


def worker_selftest() -> bool:
    """
    Call once at worker startup to verify DB connectivity and schema.
    Returns True on success, raises on failure.
    """
    log.info("Running worker self-test...")
    conn = _get_conn()
    cur  = conn.cursor()

    # Table must exist
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='audit_logs'"
    )
    assert cur.fetchone(), "audit_logs table is missing — run schema migration"

    # Write + read back a canary row, then delete it
    canary_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO audit_logs (case_id, condition_type, severity_score) "
        "VALUES (%s, %s, %s)",
        (canary_id, "__selftest__", -1),
    )
    conn.commit()

    cur.execute("SELECT id FROM audit_logs WHERE case_id=%s", (canary_id,))
    assert cur.fetchone(), "Canary row not visible after commit — DB write broken"

    cur.execute("DELETE FROM audit_logs WHERE case_id=%s", (canary_id,))
    conn.commit()
    conn.close()

    log.info("Worker self-test PASSED ✅")
    return True
