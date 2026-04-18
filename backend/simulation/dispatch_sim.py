#!/usr/bin/env python3
"""
MediRoute — Dispatch Simulation Runner
Two modes:
  1. SCENARIO: Multi-hospital load balancing across condition types
  2. BURST:    Time-series throughput stress test

Usage:
    python simulation/dispatch_sim.py --mode scenario --api http://localhost:8001
    python simulation/dispatch_sim.py --mode burst --count 50 --api http://localhost:8001
    python simulation/dispatch_sim.py --mode both --api http://localhost:8001
"""

import argparse
import json
import time
import random
import uuid
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import httpx
except ImportError:
    print("httpx required: pip install httpx")
    sys.exit(1)


# ── Hospital Network ─────────────────────────────────────────────────────────
# Realistic Dehradun/Uttarakhand hospital spread
HOSPITALS = [
    {
        "id": 1, "name": "Max Super Speciality Dehradun",
        "latitude": 30.3165, "longitude": 78.0322,
        "available_beds": 45, "total_beds": 200, "icu_beds": 12,
        "has_icu": True, "accepting": True, "hospital_type": "tertiary",
        "equipment": ["defibrillator", "ventilator", "ct_scanner", "blood_bank",
                       "or_suite", "oxygen", "ecg", "ultrasound"],
        "hospital_load": 0.4,
    },
    {
        "id": 2, "name": "Synergy Institute of Medical Sciences",
        "latitude": 30.2848, "longitude": 78.0568,
        "available_beds": 30, "total_beds": 150, "icu_beds": 8,
        "has_icu": True, "accepting": True, "hospital_type": "tertiary",
        "equipment": ["defibrillator", "ventilator", "ct_scanner", "blood_bank",
                       "oxygen", "ecg"],
        "hospital_load": 0.55,
    },
    {
        "id": 3, "name": "Doon Medical College Hospital",
        "latitude": 30.3244, "longitude": 78.0400,
        "available_beds": 80, "total_beds": 400, "icu_beds": 20,
        "has_icu": True, "accepting": True, "hospital_type": "tertiary",
        "equipment": ["defibrillator", "ventilator", "ct_scanner", "blood_bank",
                       "or_suite", "oxygen", "ecg", "ultrasound", "mri"],
        "hospital_load": 0.7,
    },
    {
        "id": 4, "name": "Shri Mahant Indiresh Hospital",
        "latitude": 30.3077, "longitude": 78.0150,
        "available_beds": 25, "total_beds": 120, "icu_beds": 4,
        "has_icu": True, "accepting": True, "hospital_type": "secondary",
        "equipment": ["ventilator", "oxygen", "ecg", "defibrillator"],
        "hospital_load": 0.35,
    },
    {
        "id": 5, "name": "Himalayan Hospital SRHU",
        "latitude": 30.3889, "longitude": 78.0748,
        "available_beds": 60, "total_beds": 300, "icu_beds": 15,
        "has_icu": True, "accepting": True, "hospital_type": "tertiary",
        "equipment": ["defibrillator", "ventilator", "ct_scanner", "blood_bank",
                       "or_suite", "oxygen", "ecg", "mri", "ultrasound"],
        "hospital_load": 0.5,
    },
    {
        "id": 6, "name": "Coronation Hospital",
        "latitude": 30.3350, "longitude": 78.0475,
        "available_beds": 15, "total_beds": 80, "icu_beds": 2,
        "has_icu": True, "accepting": True, "hospital_type": "secondary",
        "equipment": ["oxygen", "ecg", "ventilator"],
        "hospital_load": 0.6,
    },
    {
        "id": 7, "name": "Government Hospital Roorkee",
        "latitude": 29.8543, "longitude": 77.8880,
        "available_beds": 40, "total_beds": 200, "icu_beds": 6,
        "has_icu": True, "accepting": True, "hospital_type": "secondary",
        "equipment": ["oxygen", "ventilator", "ecg", "blood_bank", "defibrillator"],
        "hospital_load": 0.45,
    },
    {
        "id": 8, "name": "Rural Health Center Mussoorie",
        "latitude": 30.4598, "longitude": 78.0644,
        "available_beds": 8, "total_beds": 30, "icu_beds": 0,
        "has_icu": False, "accepting": True, "hospital_type": "primary",
        "equipment": ["oxygen", "ecg"],
        "hospital_load": 0.2,
    },
    {
        "id": 9, "name": "Primary Health Center Doiwala",
        "latitude": 30.2667, "longitude": 78.0500,
        "available_beds": 6, "total_beds": 20, "icu_beds": 0,
        "has_icu": False, "accepting": True, "hospital_type": "primary",
        "equipment": ["oxygen", "ecg"],
        "hospital_load": 0.15,
    },
]


# ── Scenario Definitions ─────────────────────────────────────────────────────
SCENARIOS = [
    {
        "name": "Cardiac arrest — central Dehradun",
        "condition_type": "cardiac_arrest",
        "severity_score": 9,
        "ambulance_lat": 30.3200, "ambulance_lng": 78.0350,
        "required_equipment": ["defibrillator"],
        "ambulance_equipment": ["oxygen", "ecg"],
        "vitals": {"spo2": 82, "pulse": 145, "systolic": 68},
    },
    {
        "name": "Stroke — south Dehradun",
        "condition_type": "stroke",
        "severity_score": 8,
        "ambulance_lat": 30.2900, "ambulance_lng": 78.0500,
        "required_equipment": ["ct_scanner"],
        "ambulance_equipment": ["oxygen"],
        "vitals": {"spo2": 91, "pulse": 95, "systolic": 160},
    },
    {
        "name": "Multi-trauma — highway accident near Roorkee",
        "condition_type": "trauma",
        "severity_score": 10,
        "ambulance_lat": 29.8700, "ambulance_lng": 77.8900,
        "required_equipment": ["blood_bank", "or_suite"],
        "ambulance_equipment": ["oxygen", "ecg"],
        "vitals": {"spo2": 78, "pulse": 135, "systolic": 60},
    },
    {
        "name": "Respiratory distress — Mussoorie hills",
        "condition_type": "respiratory",
        "severity_score": 6,
        "ambulance_lat": 30.4550, "ambulance_lng": 78.0700,
        "required_equipment": ["ventilator", "oxygen"],
        "ambulance_equipment": ["oxygen"],
        "vitals": {"spo2": 86, "pulse": 105, "systolic": 110},
    },
    {
        "name": "Mild injury — low severity urban",
        "condition_type": "default",
        "severity_score": 3,
        "ambulance_lat": 30.3150, "ambulance_lng": 78.0300,
        "required_equipment": [],
        "ambulance_equipment": ["oxygen", "ecg"],
        "vitals": {"spo2": 97, "pulse": 80, "systolic": 120},
    },
    {
        "name": "Cardiac — high load scenario (Doon MC area)",
        "condition_type": "cardiac_arrest",
        "severity_score": 9,
        "ambulance_lat": 30.3240, "ambulance_lng": 78.0410,
        "required_equipment": ["defibrillator"],
        "ambulance_equipment": ["oxygen", "defibrillator"],
        "vitals": {"spo2": 85, "pulse": 130, "systolic": 75},
    },
    {
        "name": "Stroke — remote ambulance far from tertiary",
        "condition_type": "stroke",
        "severity_score": 7,
        "ambulance_lat": 30.4200, "ambulance_lng": 78.0600,
        "required_equipment": ["ct_scanner"],
        "ambulance_equipment": ["oxygen"],
        "vitals": {"spo2": 93, "pulse": 88, "systolic": 140},
    },
    {
        "name": "Trauma — multiple equipment needs",
        "condition_type": "trauma",
        "severity_score": 9,
        "ambulance_lat": 30.3100, "ambulance_lng": 78.0200,
        "required_equipment": ["blood_bank", "or_suite", "ventilator"],
        "ambulance_equipment": ["oxygen", "ecg"],
        "vitals": {"spo2": 80, "pulse": 140, "systolic": 65},
    },
    {
        # Validates primary-center routing: low severity + close to Doiwala (30.2667, 78.0500)
        # Primary Health Center Doiwala should win — no equipment constraint, severity 2
        "name": "Minor case — near Primary Health Center Doiwala",
        "condition_type": "default",
        "severity_score": 2,
        "ambulance_lat": 30.2700, "ambulance_lng": 78.0490,
        "required_equipment": [],
        "ambulance_equipment": ["oxygen"],
        "vitals": {"spo2": 98, "pulse": 76, "systolic": 125},
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────
SEP = "═" * 70

def dispatch(client: httpx.Client, payload: dict) -> tuple[dict, float]:
    """Send a dispatch request, return (response_json, latency_ms)."""
    t0 = time.perf_counter()
    resp = client.post("/dispatch", json=payload)
    latency_ms = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    return resp.json(), latency_ms


def print_scenario_result(name: str, result: dict, latency_ms: float):
    hosp = result.get("selected_hospital") or {}
    bd = hosp.get("score_breakdown", {})
    print(f"\n  📋 {name}")
    print(f"     Decision   : {result['decision']}")
    print(f"     Hospital   : {hosp.get('name', 'N/A')}")
    print(f"     Score      : {hosp.get('score', 0):.1f}/100")
    print(f"     Distance   : {bd.get('distance_km', '?')} km")
    print(f"     Equipment  : matched={bd.get('equipment_matched', [])}")
    if bd.get("equipment_missing"):
        print(f"                  missing={bd['equipment_missing']}")
    print(f"     ICU        : {bd.get('icu', 0):.0f}/10")
    print(f"     Load       : {bd.get('load', 0):.1f}/10")
    print(f"     Queued     : {result['queued']}  job_id={result['job_id'][:12]}...")
    print(f"     Latency    : {latency_ms:.0f} ms")
    if result.get("reasoning"):
        for r in result["reasoning"]:
            print(f"     ⚠ {r}")


# ── Mode 1: Scenario-based simulation ────────────────────────────────────────
def run_scenarios(api_url: str):
    print(f"\n{SEP}")
    print("  MODE 1: MULTI-HOSPITAL LOAD BALANCING SCENARIOS")
    print(f"{SEP}")

    client = httpx.Client(base_url=api_url, timeout=30)
    results = []
    hospital_dispatch_count: dict[str, int] = {}

    for sc in SCENARIOS:
        payload = {
            "hospitals": HOSPITALS,
            "ambulance_lat": sc["ambulance_lat"],
            "ambulance_lng": sc["ambulance_lng"],
            "condition_type": sc["condition_type"],
            "severity_score": sc["severity_score"],
            "required_equipment": sc["required_equipment"],
            "ambulance_equipment": sc["ambulance_equipment"],
            "vitals": sc["vitals"],
        }
        try:
            result, latency = dispatch(client, payload)
            print_scenario_result(sc["name"], result, latency)
            hosp_name = result.get("selected_hospital", {}).get("name", "N/A")
            hospital_dispatch_count[hosp_name] = hospital_dispatch_count.get(hosp_name, 0) + 1
            results.append({"scenario": sc["name"], "hospital": hosp_name,
                            "score": result["selected_hospital"]["score"],
                            "latency_ms": latency, "queued": result["queued"]})
        except Exception as e:
            print(f"\n  ❌ {sc['name']}: {e}")
            results.append({"scenario": sc["name"], "error": str(e)})

    # Summary
    print(f"\n{SEP}")
    print("  LOAD BALANCING SUMMARY")
    print(f"{SEP}")
    print(f"  Scenarios run: {len(SCENARIOS)}")
    scores = [r["score"] for r in results if "score" in r]
    latencies = [r["latency_ms"] for r in results if "latency_ms" in r]
    if scores:
        print(f"  Avg score    : {sum(scores)/len(scores):.1f}")
        print(f"  Min/Max      : {min(scores):.1f} / {max(scores):.1f}")
    if latencies:
        print(f"  Avg latency  : {sum(latencies)/len(latencies):.0f} ms")
        print(f"  P99 latency  : {sorted(latencies)[int(len(latencies)*0.99)]:.0f} ms")
    print(f"\n  Hospital distribution:")
    for h, count in sorted(hospital_dispatch_count.items(), key=lambda x: -x[1]):
        bar = "█" * count + "░" * (len(SCENARIOS) - count)
        print(f"    {h:40s} {bar} ({count})")

    client.close()
    return results


# ── Mode 2: Burst throughput test ─────────────────────────────────────────────
def run_burst(api_url: str, count: int = 50, concurrency: int = 5):
    print(f"\n{SEP}")
    print(f"  MODE 2: BURST THROUGHPUT TEST ({count} dispatches, {concurrency} concurrent)")
    print(f"{SEP}")

    conditions = ["cardiac_arrest", "stroke", "trauma", "respiratory", "default"]
    latencies = []
    errors = 0
    queued_count = 0

    def fire_one(i: int) -> tuple[int, float, bool, str | None]:
        client = httpx.Client(base_url=api_url, timeout=30)
        cond = random.choice(conditions)
        sev = random.randint(1, 10)
        payload = {
            "hospitals": HOSPITALS,
            "ambulance_lat": 30.3165 + random.uniform(-0.05, 0.05),
            "ambulance_lng": 78.0322 + random.uniform(-0.05, 0.05),
            "condition_type": cond,
            "severity_score": sev,
            "required_equipment": random.sample(
                ["defibrillator", "ventilator", "oxygen", "ct_scanner", "blood_bank"],
                k=random.randint(0, 2)
            ),
            "ambulance_equipment": ["oxygen"],
            "vitals": {
                "spo2": random.randint(75, 99),
                "pulse": random.randint(60, 150),
                "systolic": random.randint(60, 160),
            },
        }
        try:
            result, lat = dispatch(client, payload)
            client.close()
            return i, lat, result["queued"], None
        except Exception as e:
            client.close()
            return i, 0.0, False, str(e)

    t_start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(fire_one, i) for i in range(count)]
        for f in as_completed(futures):
            idx, lat, q, err = f.result()
            if err:
                errors += 1
                sys.stdout.write("✗")
            else:
                latencies.append(lat)
                if q:
                    queued_count += 1
                sys.stdout.write("·")
            sys.stdout.flush()

    elapsed = time.perf_counter() - t_start
    print()

    # Stats
    print(f"\n{SEP}")
    print("  BURST RESULTS")
    print(f"{SEP}")
    print(f"  Total dispatches  : {count}")
    print(f"  Successful        : {len(latencies)}")
    print(f"  Errors            : {errors}")
    print(f"  Queued to RQ      : {queued_count}/{len(latencies)}")
    print(f"  Wall clock        : {elapsed:.2f}s")
    print(f"  Throughput        : {len(latencies)/elapsed:.1f} req/s")
    if latencies:
        latencies.sort()
        print(f"  Latency (avg)     : {sum(latencies)/len(latencies):.0f} ms")
        print(f"  Latency (p50)     : {latencies[len(latencies)//2]:.0f} ms")
        print(f"  Latency (p95)     : {latencies[int(len(latencies)*0.95)]:.0f} ms")
        print(f"  Latency (p99)     : {latencies[int(len(latencies)*0.99)]:.0f} ms")
        print(f"  Latency (min/max) : {latencies[0]:.0f} / {latencies[-1]:.0f} ms")

    return {"total": count, "ok": len(latencies), "errors": errors,
            "queued": queued_count, "elapsed_s": elapsed}


# ── Post-run: fetch /metrics to confirm DB persistence ────────────────────────
def check_metrics(api_url: str):
    print(f"\n{SEP}")
    print("  POST-SIMULATION /metrics CHECK")
    print(f"{SEP}")

    client = httpx.Client(base_url=api_url, timeout=10)
    try:
        resp = client.get("/metrics", params={"hours": 1})
        resp.raise_for_status()
        m = resp.json()
        s = m["summary"]
        print(f"  Window          : last {m['window_hours']}h (since {m['since'][:19]})")
        print(f"  Total cases     : {s['total_cases']}")
        print(f"  Avg severity    : {s['avg_severity']:.1f}" if s['avg_severity'] else "  Avg severity    : N/A")
        print(f"  Avg hosp score  : {s['avg_hospital_score']:.1f}" if s['avg_hospital_score'] else "  Avg hosp score  : N/A")
        print(f"  Critical (≥8)   : {s['critical_cases']}")
        print(f"  Hospitals used  : {s['hospitals_used']}")
        if m.get("by_condition"):
            print(f"\n  By condition:")
            for c in m["by_condition"]:
                print(f"    {c['condition_type']:25s} {c['n']} cases")
        if m.get("by_hospital"):
            print(f"\n  By hospital:")
            for h in m["by_hospital"]:
                avg = f"{h['avg_score']:.1f}" if h['avg_score'] else "N/A"
                print(f"    {h['selected_hospital_name']:40s} {h['dispatches']} dispatches  avg_score={avg}")
    except Exception as e:
        print(f"  ❌ /metrics failed: {e}")
    client.close()


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="MediRoute dispatch simulation")
    parser.add_argument("--mode", choices=["scenario", "burst", "both"], default="both")
    parser.add_argument("--api", default="http://localhost:8001", help="API base URL")
    parser.add_argument("--count", type=int, default=50, help="Burst dispatch count")
    parser.add_argument("--concurrency", type=int, default=5, help="Burst concurrency")
    args = parser.parse_args()

    print(f"\n{'═'*70}")
    print(f"  MEDIROUTE DISPATCH SIMULATION")
    print(f"  API: {args.api}  |  Mode: {args.mode}")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"{'═'*70}")

    # Health check
    try:
        r = httpx.get(f"{args.api}/health", timeout=5)
        h = r.json()
        print(f"\n  Health: api={h['api']}  redis={h['redis']}  db={h['db']}")
        if h["redis"] != "ok" or h["db"] != "ok":
            print("  ⚠ Redis or DB not healthy — results may be incomplete")
    except Exception as e:
        print(f"\n  ❌ Cannot reach API: {e}")
        sys.exit(1)

    if args.mode in ("scenario", "both"):
        run_scenarios(args.api)

    if args.mode in ("burst", "both"):
        run_burst(args.api, count=args.count, concurrency=args.concurrency)

    # Always check metrics after
    # Give the worker 2s to drain the queue
    print("\n  ⏳ Waiting 3s for RQ worker to drain queue...")
    time.sleep(3)
    check_metrics(args.api)

    print(f"\n{'═'*70}")
    print("  SIMULATION COMPLETE")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    main()
