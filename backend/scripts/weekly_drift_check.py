"""
weekly_drift_check.py - Passive scoring drift detection from production data.

Queries the last N days of DecisionCandidate rows (plus CaseEvent for ETA accuracy)
and prints a drift report. Run weekly via cron or Celery beat:

    # crontab (weekly Monday 06:00)
    0 6 * * 1 cd /app && python scripts/weekly_drift_check.py >> logs/drift.log 2>&1

    # or: python scripts/weekly_drift_check.py --days 14

No schema changes required. All data is already in DecisionCandidate.score_breakdown.

Drift signals computed:
  1. Mean S_treatment of selected hospitals (leading indicator of hospital data decay)
  2. Mean S_eta of selected hospitals (flags if ETA scoring balance shifts)
  3. Mean final score of selected hospitals (overall quality proxy)
  4. Low-bed selections (available_beds < 3 at dispatch time - load signal)
  5. ETA accuracy proxy: time from Case.created_at to CaseEvent(status='arrived')
     vs DecisionCandidate.eta_minutes for the selected hospital.

Usage:
    python scripts/weekly_drift_check.py [--days N] [--db-url URL]
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import statistics
from datetime import datetime, timedelta, timezone

# ── path bootstrap ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("MODEL_SHA256", os.getenv("MODEL_SHA256", ""))
os.environ.setdefault("DISABLE_DRIFT_CHECK", "1")
os.environ.setdefault("DISABLE_LEARNING_UPDATE", "1")

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Case, CaseEvent, DecisionCandidate

logging.basicConfig(level=logging.WARNING)
log = logging.getLogger(__name__)

# ── thresholds ────────────────────────────────────────────────────────────────
# Alert if mean S_treatment of selected hospitals falls below this.
# 0.6 = most selected hospitals should have some relevant specialty capability.
S_TREATMENT_FLOOR = 0.60

# Alert if mean final score of selected hospitals falls below this.
# Scores near 0.5 suggest the engine is making low-confidence picks consistently.
FINAL_SCORE_FLOOR = 0.55

# Alert if more than this fraction of selected hospitals had < 3 available beds.
# High value = load constraint is not filtering tight enough (or data is stale).
LOW_BEDS_FRACTION_THRESHOLD = 0.20

# ETA accuracy: flag cases where actual transit time deviated more than this
# many minutes from the estimated eta_minutes at dispatch.
ETA_ACCURACY_NOISE_THRESHOLD = 10.0  # minutes


def _get_db_url() -> str:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        # Try loading from .env in parent of scripts/
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            for line in open(env_path):
                line = line.strip()
                if line.startswith("DATABASE_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    return url


def run_drift_check(db: Session, days: int = 7) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # ── 1. Pull selected DecisionCandidate rows ───────────────────────────────
    rows: list[DecisionCandidate] = (
        db.query(DecisionCandidate)
        .join(Case, DecisionCandidate.case_id == Case.id)
        .filter(
            Case.created_at >= cutoff,
            DecisionCandidate.is_selected == True,  # noqa: E712
        )
        .all()
    )

    if not rows:
        return {"decisions": 0, "message": f"No decisions in last {days} days."}

    scores         = [r.score for r in rows if r.score is not None]
    breakdowns     = [r.score_breakdown for r in rows if r.score_breakdown]
    beds_snapshots = [r.available_beds_snapshot for r in rows]
    eta_estimates  = {r.case_id: r.eta_minutes for r in rows}  # case_id → estimated ETA

    s_treatment_vals = [b.get("S_treatment", 0.0) for b in breakdowns if b]
    s_eta_vals       = [b.get("S_eta", 0.0)       for b in breakdowns if b]
    s_survival_vals  = [b.get("S_survival", 0.0)  for b in breakdowns if b]

    low_bed_count = sum(1 for b in beds_snapshots if b is not None and b < 3)

    # ── 2. ETA accuracy - compare estimated vs actual transit time ────────────
    # "Actual" = timestamp of first CaseEvent with status='arrived'
    #          minus Case.created_at (dispatch time).
    # This is a proxy: it includes any pre-dispatch delay on the ambulance side,
    # but over many cases the mean should track ETA estimate accuracy.
    case_ids = list(eta_estimates.keys())
    arrived_events: list[CaseEvent] = (
        db.query(CaseEvent)
        .join(Case, CaseEvent.case_id == Case.id)
        .filter(
            CaseEvent.case_id.in_(case_ids),
            CaseEvent.status == "arrived",
        )
        .all()
    ) if case_ids else []

    # Build case_id → Case.created_at map for the relevant cases
    cases_map: dict[int, datetime] = {}
    if case_ids:
        for case in db.query(Case).filter(Case.id.in_(case_ids)).all():
            cases_map[case.id] = case.created_at

    eta_errors: list[float] = []
    for ev in arrived_events:
        case_created = cases_map.get(ev.case_id)
        est_eta      = eta_estimates.get(ev.case_id)
        if case_created and est_eta and ev.timestamp:
            if ev.actual_eta_minutes is not None:
                actual_minutes = ev.actual_eta_minutes
            else:
                # Normalize timezone: arrived_timestamp - dispatch_timestamp
                arrived_ts = ev.timestamp
                if arrived_ts.tzinfo is None:
                    arrived_ts = arrived_ts.replace(tzinfo=timezone.utc)
                if case_created.tzinfo is None:
                    case_created = case_created.replace(tzinfo=timezone.utc)
                actual_minutes = (arrived_ts - case_created).total_seconds() / 60.0
            
            if 0 < actual_minutes < 120:  # ignore implausible values
                eta_errors.append(abs(actual_minutes - est_eta))

    # ── 3. Build report ───────────────────────────────────────────────────────
    report: dict = {
        "period_days":    days,
        "cutoff":         cutoff.isoformat(),
        "decisions":      len(rows),
        "with_breakdown": len(breakdowns),
        "arrived_events": len(arrived_events),
    }

    alerts: list[str] = []

    def _stat(vals: list[float], label: str) -> dict:
        if not vals:
            return {"n": 0, "mean": None, "stdev": None, "min": None, "max": None}
        return {
            "n":     len(vals),
            "mean":  round(statistics.mean(vals), 4),
            "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
            "min":   round(min(vals), 4),
            "max":   round(max(vals), 4),
        }

    report["final_score"]   = _stat(scores,          "final_score")
    report["S_treatment"]   = _stat(s_treatment_vals, "S_treatment")
    report["S_eta"]         = _stat(s_eta_vals,        "S_eta")
    report["S_survival"]    = _stat(s_survival_vals,   "S_survival")
    report["eta_error_min"] = _stat(eta_errors,        "eta_error_min")

    low_beds_frac = low_bed_count / len(rows)
    report["low_bed_selections"] = {
        "count":    low_bed_count,
        "total":    len(rows),
        "fraction": round(low_beds_frac, 3),
    }

    # ── 4. Alert conditions ───────────────────────────────────────────────────
    if s_treatment_vals and statistics.mean(s_treatment_vals) < S_TREATMENT_FLOOR:
        alerts.append(
            f"WARNING: S_treatment mean {statistics.mean(s_treatment_vals):.3f} < "
            f"{S_TREATMENT_FLOOR} - check hospital specialty data quality or "
            f"capability constraint relaxation."
        )

    if scores and statistics.mean(scores) < FINAL_SCORE_FLOOR:
        alerts.append(
            f"WARNING: Mean final score {statistics.mean(scores):.3f} < "
            f"{FINAL_SCORE_FLOOR} - engine consistently choosing low-confidence "
            f"candidates. Check hard constraint filtering."
        )

    if low_beds_frac > LOW_BEDS_FRACTION_THRESHOLD:
        alerts.append(
            f"WARNING: {low_bed_count}/{len(rows)} ({low_beds_frac:.0%}) selected hospitals "
            f"had < 3 available beds at dispatch - load gating may be too loose "
            f"or hospital availability data is stale."
        )

    if eta_errors:
        mean_error = statistics.mean(eta_errors)
        if mean_error > ETA_ACCURACY_NOISE_THRESHOLD:
            alerts.append(
                f"WARNING: Mean ETA error {mean_error:.1f} min > "
                f"{ETA_ACCURACY_NOISE_THRESHOLD} min across {len(eta_errors)} "
                f"cases with arrival data - routing service estimates may be "
                f"systematically off. Check ORS/Google Maps traffic model."
            )

    report["alerts"] = alerts
    return report


def _print_report(r: dict) -> None:
    bar = "=" * 72
    print(f"\n{bar}")
    print(f"MediRoute Drift Check  |  Last {r.get('period_days', '?')} days  |  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(bar)

    if r.get("decisions", 0) == 0:
        print(f"\n  {r.get('message', 'No data.')}")
        return

    print(f"\n  Decisions analysed : {r['decisions']}")
    print(f"  With score_breakdown: {r['with_breakdown']}")
    print(f"  Arrived events      : {r['arrived_events']}")

    def _row(label: str, stat: dict) -> str:
        if stat["n"] == 0:
            return f"  {label:<18}  n=0  (no data)"
        return (
            f"  {label:<18}  n={stat['n']:<4}  "
            f"mean={stat['mean']:.4f}  "
            f"stdev={stat['stdev']:.4f}  "
            f"[{stat['min']:.4f}, {stat['max']:.4f}]"
        )

    print()
    print("  Component score distributions (selected hospitals only):")
    print("  " + "-" * 68)
    print(_row("final_score",   r["final_score"]))
    print(_row("S_treatment",   r["S_treatment"]))
    print(_row("S_eta",         r["S_eta"]))
    print(_row("S_survival",    r["S_survival"]))

    print()
    lb = r["low_bed_selections"]
    print(f"  Low-bed selections  : {lb['count']}/{lb['total']}  ({lb['fraction']:.0%} of dispatches had <3 beds available)")

    eta_err = r["eta_error_min"]
    if eta_err["n"] > 0:
        print(f"  ETA accuracy (proxy): n={eta_err['n']}  mean_error={eta_err['mean']:.1f} min  max_error={eta_err['max']:.1f} min")
    else:
        print("  ETA accuracy        : no 'arrived' events yet - ambulance timeline not yet populating.")

    print()
    alerts = r.get("alerts", [])
    if alerts:
        print("  ALERTS:")
        for a in alerts:
            print(f"    {a}")
    else:
        print("  OK: No alerts - all metrics within acceptable bounds.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="MediRoute weekly drift check")
    parser.add_argument("--days",   type=int, default=7,  help="Lookback window in days (default: 7)")
    parser.add_argument("--db-url", type=str, default="", help="Override DATABASE_URL")
    args = parser.parse_args()

    db_url = args.db_url or _get_db_url()
    if not db_url:
        print("ERROR: DATABASE_URL not set. Pass --db-url or set the env var.")
        sys.exit(1)

    engine = create_engine(db_url, echo=False, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine)

    with SessionLocal() as db:
        report = run_drift_check(db, days=args.days)

    _print_report(report)

    # Exit 1 if any alerts - lets cron jobs surface failures via exit code
    if report.get("alerts"):
        sys.exit(1)


if __name__ == "__main__":
    main()
