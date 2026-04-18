#!/usr/bin/env python3
"""
MediRoute — Persistence Debugger
Traces the full audit_logs commit path and pinpoints exactly where data is lost.

Tests in order:
  1. Direct psycopg2 INSERT (bypasses everything — is PG itself writable?)
  2. Connection string parsing (is DATABASE_URL pointing at Docker or local PG?)
  3. Transaction isolation (is COMMIT actually firing, or is autocommit off?)
  4. RQ job simulation (does the worker task function commit correctly?)
  5. Row visibility (can the querying connection see committed rows?)
"""

import os
import sys
import uuid
import json
import traceback
import psycopg2
import psycopg2.extras
import redis
from datetime import datetime, timezone

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mediroute")
REDIS_URL    = os.getenv("REDIS_URL",    "redis://localhost:6379/0")

CASE_ID = str(uuid.uuid4())

SEP  = "─" * 60
PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"
INFO = "  ℹ️  "

def section(title):
    print(f"\n{SEP}\nTEST: {title}\n{SEP}")

def get_conn(dsn=None):
    return psycopg2.connect(dsn or DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)

# ──────────────────────────────────────────────────────────
# 1. Connection target — what host/port/db are we hitting?
# ──────────────────────────────────────────────────────────
section("1. Connection target")
print(f"{INFO}DATABASE_URL = {DATABASE_URL}")
print(f"{INFO}REDIS_URL    = {REDIS_URL}")
try:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT current_database(), inet_server_addr(), inet_server_port(), version()")
    row = cur.fetchone()
    print(f"{PASS}Connected to DB  : {row['current_database']}")
    print(f"{INFO}  Server address : {row['inet_server_addr']}")
    print(f"{INFO}  Server port    : {row['inet_server_port']}")
    print(f"{INFO}  PG version     : {row['version'][:40]}")
    conn.close()
except Exception as e:
    print(f"{FAIL}Cannot connect: {e}")
    print("     ↳ Worker is probably pointing at a DIFFERENT host than your docker container.")
    print("       Check DATABASE_URL env var in the shell where rq worker runs.")
    sys.exit(1)

# ──────────────────────────────────────────────────────────
# 2. Table existence check
# ──────────────────────────────────────────────────────────
section("2. audit_logs table")
try:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        SELECT table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name)))
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = 'audit_logs'
    """)
    row = cur.fetchone()
    if row:
        print(f"{PASS}Table exists ({row['pg_size_pretty']})")
        cur.execute("SELECT COUNT(*) AS n FROM audit_logs")
        print(f"{INFO}  Current row count: {cur.fetchone()['n']}")
    else:
        print(f"{FAIL}Table does NOT exist — run the schema migration first.")
        conn.close()
        sys.exit(1)
    conn.close()
except Exception as e:
    print(f"{FAIL}{e}")
    sys.exit(1)

# ──────────────────────────────────────────────────────────
# 3. Raw INSERT + COMMIT (no ORM, no framework)
# ──────────────────────────────────────────────────────────
section("3. Raw psycopg2 INSERT → explicit COMMIT")
raw_id = str(uuid.uuid4())
try:
    conn = get_conn()
    conn.autocommit = False          # explicit transaction
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO audit_logs (
            case_id, condition_type, severity_score,
            ambulance_lat, ambulance_lng,
            selected_hospital_id, selected_hospital_name,
            score, score_breakdown, vitals,
            required_equipment, ambulance_equipment, all_hospitals
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb
        )
    """, (
        raw_id, "diagnostic_raw", 1,
        30.31, 78.03,
        0, "DiagnosticHospital",
        0.0, json.dumps({}), json.dumps({"test": True}),
        ["oxygen"], ["oxygen"],
        json.dumps([])
    ))
    conn.commit()
    print(f"{PASS}INSERT + COMMIT executed")
    conn.close()
except Exception as e:
    print(f"{FAIL}INSERT failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# Now verify with a FRESH connection (different conn = different transaction)
try:
    conn2 = get_conn()
    cur2  = conn2.cursor()
    cur2.execute("SELECT id FROM audit_logs WHERE case_id = %s", (raw_id,))
    row = cur2.fetchone()
    if row:
        print(f"{PASS}Row visible on fresh connection (id={row['id']})")
    else:
        print(f"{FAIL}Row NOT visible on fresh connection — possible COMMIT silently failed")
        print("     ↳ Check: is psycopg2 in autocommit=True mode somewhere that swallowed the error?")
    conn2.close()
except Exception as e:
    print(f"{FAIL}{e}")

# ──────────────────────────────────────────────────────────
# 4. Simulate exactly what the RQ worker task does
#    (mirrors your worker/tasks.py logic)
# ──────────────────────────────────────────────────────────
section("4. Worker task simulation (exact replica of tasks.py logic)")

def simulate_worker_commit(case_id: str, payload: dict):
    """Mirrors the worker's audit_log task — if THIS fails, the bug is in task logic."""
    db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mediroute")
    conn = psycopg2.connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (
                case_id, condition_type, severity_score,
                ambulance_lat, ambulance_lng,
                selected_hospital_id, selected_hospital_name,
                score, score_breakdown, vitals,
                required_equipment, ambulance_equipment, all_hospitals
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb
            )
        """, (
            case_id,
            payload.get("condition_type"),
            payload.get("severity_score"),
            payload.get("ambulance_lat"),
            payload.get("ambulance_lng"),
            payload.get("selected_hospital_id", 0),
            payload.get("selected_hospital_name", ""),
            payload.get("score", 0.0),
            json.dumps(payload.get("score_breakdown", {})),
            json.dumps(payload.get("vitals", {})),
            payload.get("required_equipment", []),
            payload.get("ambulance_equipment", []),
            json.dumps(payload.get("all_hospitals", [])),
        ))
        conn.commit()
        print(f"  Worker: COMMITTED case_id={case_id}")
    except Exception as e:
        conn.rollback()
        print(f"  Worker: ROLLED BACK — {e}")
        raise
    finally:
        conn.close()

sim_id = str(uuid.uuid4())
sample_payload = {
    "condition_type": "cardiac_arrest",
    "severity_score": 8,
    "ambulance_lat": 30.3165,
    "ambulance_lng": 78.0322,
    "selected_hospital_id": 1,
    "selected_hospital_name": "City Cardiac Center",
    "score": 72.5,
    "score_breakdown": {"distance": 0.3, "load": 0.4, "equipment": 0.3},
    "vitals": {"spo2": 88, "pulse": 110, "systolic": 90},
    "required_equipment": ["defibrillator"],
    "ambulance_equipment": ["oxygen"],
    "all_hospitals": [],
}

try:
    simulate_worker_commit(sim_id, sample_payload)
    # Verify
    conn3 = get_conn()
    cur3  = conn3.cursor()
    cur3.execute("SELECT id, selected_hospital_name FROM audit_logs WHERE case_id = %s", (sim_id,))
    row = cur3.fetchone()
    if row:
        print(f"{PASS}Worker simulation row visible (id={row['id']}, hospital={row['selected_hospital_name']})")
    else:
        print(f"{FAIL}Worker simulation row NOT visible — task is committing to wrong DB or rolling back")
    conn3.close()
except Exception as e:
    print(f"{FAIL}Worker simulation threw: {e}")
    traceback.print_exc()

# ──────────────────────────────────────────────────────────
# 5. Redis connectivity (worker job queue)
# ──────────────────────────────────────────────────────────
section("5. Redis queue connectivity")
try:
    r = redis.from_url(REDIS_URL)
    pong = r.ping()
    print(f"{PASS}Redis PING → {pong}")
    queues = r.keys("rq:queue:*")
    print(f"{INFO}  RQ queues visible: {[q.decode() for q in queues]}")
    failed = r.llen("rq:queue:failed")
    print(f"{INFO}  Jobs in failed queue: {failed}")
    if failed > 0:
        print(f"     ↳ IMPORTANT: There are {failed} failed jobs. Run:")
        print(f"       rq info --url {REDIS_URL}")
        print(f"       to see the failure tracebacks.")
except Exception as e:
    print(f"{FAIL}Redis error: {e}")

# ──────────────────────────────────────────────────────────
# 6. Final row count
# ──────────────────────────────────────────────────────────
section("6. Final state")
try:
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM audit_logs")
    total = cur.fetchone()['n']
    cur.execute("""
        SELECT case_id, condition_type, severity_score, timestamp
        FROM audit_logs ORDER BY timestamp DESC LIMIT 5
    """)
    rows = cur.fetchall()
    print(f"{PASS}Total rows in audit_logs: {total}")
    for r in rows:
        print(f"  [{r['timestamp']}] {r['condition_type']} sev={r['severity_score']} case={r['case_id']}")
    conn.close()
except Exception as e:
    print(f"{FAIL}{e}")

print(f"\n{'═'*60}")
print("DIAGNOSIS COMPLETE")
print(f"{'═'*60}\n")
print("If tests 3 & 4 pass but your actual worker inserts 0 rows:")
print("  → The worker process is using a different DATABASE_URL")
print("     (likely pointing at localhost:5432 on the HOST machine,")
print("      not the Docker container's mapped port)")
print("")
print("Fix: In the terminal where you run 'rq worker', set:")
print("  export DATABASE_URL=postgresql://postgres:postgres@localhost:<DOCKER_PORT>/mediroute")
print("  (check 'docker ps' for the host port mapped to 5432 in the DB container)")
