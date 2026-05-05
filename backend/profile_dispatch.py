import time
import asyncio
import sys
sys.path.insert(0, '/app')

from app.db.database import SessionLocal
from app.engine import dispatch_engine
from app.services.eta_service import set_haversine_only_mode
set_haversine_only_mode(True)

db = SessionLocal()

# Phase 1: DB snapshot
t0 = time.perf_counter()
hospitals = dispatch_engine.get_latest_hospital_snapshots(db)
t1 = time.perf_counter()
print(f"[PHASE 1] get_latest_hospital_snapshots: {(t1-t0)*1000:.1f}ms  count={len(hospitals)}")

async def test_all():
    # Phase 2: ETA map
    t0 = time.perf_counter()
    eta_map = await dispatch_engine._fetch_eta_map(
        origin_lat=29.86, origin_lng=77.88, hospitals=hospitals
    )
    t1 = time.perf_counter()
    print(f"[PHASE 2] _fetch_eta_map: {(t1-t0)*1000:.1f}ms  map={eta_map}")

    # Phase 3: full dispatch
    t0 = time.perf_counter()
    result = await dispatch_engine.run_dispatch(
        hospitals=hospitals,
        ambulance_lat=29.86,
        ambulance_lng=77.88,
        condition_type="cardiac_arrest",
        severity_score=9,
        vitals={"oxygen": 88, "pulse": 120, "systolic": 90, "diastolic": 60},
        ambulance_equipment=["oxygen", "defibrillator", "ecg"],
        required_equipment=["defibrillator", "ecg"],
    )
    t1 = time.perf_counter()
    decision_type = (result.get("decision") or {}).get("decision_type", "?")
    print(f"[PHASE 3] run_dispatch: {(t1-t0)*1000:.1f}ms  decision={decision_type}")

    # Phase 4: second run (caches warm)
    t0 = time.perf_counter()
    result2 = await dispatch_engine.run_dispatch(
        hospitals=hospitals,
        ambulance_lat=29.86,
        ambulance_lng=77.88,
        condition_type="stroke",
        severity_score=8,
        vitals={"oxygen": 92, "pulse": 100, "systolic": 160, "diastolic": 90},
        ambulance_equipment=["oxygen", "ecg"],
        required_equipment=["ct_scan", "ecg"],
    )
    t1 = time.perf_counter()
    decision_type2 = (result2.get("decision") or {}).get("decision_type", "?")
    print(f"[PHASE 4] run_dispatch(warm): {(t1-t0)*1000:.1f}ms  decision={decision_type2}")

asyncio.run(test_all())
db.close()
