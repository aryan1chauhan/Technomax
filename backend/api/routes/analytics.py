"""
MediRoute — /metrics and /replay/{case_id} routes
"""
from __future__ import annotations

import os
import logging
from datetime import datetime, timezone, timedelta

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException, Query

log = logging.getLogger(__name__)
router = APIRouter()

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/mediroute")




@router.get("/metrics")
def metrics(
    hours: int = Query(default=24, ge=1, le=168, description="Lookback window in hours"),
):
    """Aggregate statistics over recent dispatch decisions."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        with psycopg2.connect(DATABASE_URL,
                              cursor_factory=psycopg2.extras.RealDictCursor) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        COUNT(*)                                    AS total_cases,
                        AVG(severity_score)::float                         AS avg_severity,
                        AVG(score)::float                                  AS avg_hospital_score,
                        COUNT(*) FILTER (WHERE severity_score >= 8) AS critical_cases,
                        COUNT(DISTINCT selected_hospital_name)      AS hospitals_used
                    FROM audit_logs
                    WHERE timestamp >= %s
                      AND condition_type NOT IN ('__selftest__', 'diagnostic_raw')
                """, (since,))
                summary = dict(cur.fetchone())

                cur.execute("""
                    SELECT condition_type, COUNT(*) AS n
                    FROM audit_logs
                    WHERE timestamp >= %s
                      AND condition_type NOT IN ('__selftest__', 'diagnostic_raw')
                    GROUP BY condition_type
                    ORDER BY n DESC
                """, (since,))
                by_condition = [dict(r) for r in cur.fetchall()]

                cur.execute("""
                    SELECT selected_hospital_name,
                           COUNT(*)   AS dispatches,
                           AVG(score)::float AS avg_score
                    FROM audit_logs
                    WHERE timestamp >= %s
                      AND condition_type NOT IN ('__selftest__', 'diagnostic_raw')
                    GROUP BY selected_hospital_name
                    ORDER BY dispatches DESC
                    LIMIT 10
                """, (since,))
                by_hospital = [dict(r) for r in cur.fetchall()]

        return {
            "window_hours": hours,
            "since":        since.isoformat(),
            "summary":      summary,
            "by_condition": by_condition,
            "by_hospital":  by_hospital,
        }
    except Exception as e:
        log.error("/metrics error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/{case_id}")
def replay(case_id: str):
    """Return the full audit record for a given case_id."""
    try:
        with psycopg2.connect(DATABASE_URL,
                              cursor_factory=psycopg2.extras.RealDictCursor) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM audit_logs WHERE case_id = %s", (case_id,))
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"case_id {case_id} not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        log.error("/replay error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
