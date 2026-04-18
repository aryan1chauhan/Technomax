"""
MediRoute — Hospital scoring engine.
Pure functions only — no I/O, no side effects, fully unit-testable.
"""
from __future__ import annotations
import math
from typing import Any


# ── Condition → required capability map ──────────────────────────────────────
CONDITION_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "cardiac_arrest": {
        "preferred_type": "tertiary",
        "critical_equipment": ["defibrillator"],
        "min_icu_beds": 1,
        "severity_weight": 1.4,
    },
    "stroke": {
        "preferred_type": "tertiary",
        "critical_equipment": ["ct_scanner"],
        "min_icu_beds": 1,
        "severity_weight": 1.3,
    },
    "trauma": {
        "preferred_type": "tertiary",
        "critical_equipment": ["blood_bank", "or_suite"],
        "min_icu_beds": 2,
        "severity_weight": 1.2,
    },
    "respiratory": {
        "preferred_type": "secondary",
        "critical_equipment": ["ventilator", "oxygen"],
        "min_icu_beds": 0,
        "severity_weight": 1.1,
    },
    "default": {
        "preferred_type": "secondary",
        "critical_equipment": [],
        "min_icu_beds": 0,
        "severity_weight": 1.0,
    },
}

# ── Vital-sign thresholds that trigger stabilisation ─────────────────────────
STABILISE_THRESHOLDS = {
    "spo2":     {"critical": 85,  "warning": 90},
    "systolic": {"critical": 70,  "warning": 85},
    "pulse":    {"critical": 140, "warning": 120},
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def vitals_decision(vitals: dict) -> tuple[str, list[str]]:
    """
    Returns (decision, reasons).
    decision: 'stabilize_first' | 'transport_now'
    """
    reasons: list[str] = []
    for key, thresholds in STABILISE_THRESHOLDS.items():
        val = vitals.get(key)
        if val is None:
            continue
        if key == "pulse":
            if val >= thresholds["critical"]:
                reasons.append(f"pulse critical ({val} ≥ {thresholds['critical']})")
            elif val >= thresholds["warning"]:
                reasons.append(f"pulse elevated ({val} ≥ {thresholds['warning']})")
        else:
            if val <= thresholds["critical"]:
                reasons.append(f"{key} critical ({val} ≤ {thresholds['critical']})")
            elif val <= thresholds["warning"]:
                reasons.append(f"{key} low ({val} ≤ {thresholds['warning']})")

    decision = "stabilize_first" if reasons else "transport_now"
    return decision, reasons


def score_hospital(
    hospital: dict,
    ambulance_lat: float,
    ambulance_lng: float,
    condition_type: str,
    severity_score: int,
    required_equipment: list[str],
) -> tuple[float, dict]:
    """Returns (total_score, breakdown_dict). Higher = better."""
    reqs = CONDITION_REQUIREMENTS.get(condition_type, CONDITION_REQUIREMENTS["default"])
    breakdown: dict[str, float] = {}

    # ── Score budget: availability=20, distance=25, equipment=25, load=20, ICU=10 → max=100
    # 1. Availability (0–20 pts)
    if not hospital.get("accepting", False):
        return 0.0, {"disqualified": "not_accepting"}
    avail_ratio = hospital.get("available_beds", 0) / max(hospital.get("total_beds", 1), 1)
    availability_score = avail_ratio * 20
    breakdown["availability"] = round(availability_score, 2)

    # 2. Distance (0–25 pts, inverse — closer is better)
    dist_km = haversine_km(
        ambulance_lat, ambulance_lng,
        hospital["latitude"], hospital["longitude"]
    )
    distance_score = max(0, 25 - (dist_km * 2.5))
    breakdown["distance"]      = round(distance_score, 2)
    breakdown["distance_km"]   = round(dist_km, 2)

    # 3. Equipment match (0–25 pts)
    hosp_equip = set(hospital.get("equipment", []))

    # Hard gate: caller-specified required_equipment must ALL be present.
    # critical_equipment (system-defined) is kept as a soft scoring penalty —
    # this prevents a 422 when a whole network lacks a device (e.g. rural ct_scanner).
    hard_required = set(required_equipment)
    if hard_required and not hard_required.issubset(hosp_equip):
        return 0.0, {
            "disqualified": "missing_required_equipment",
            "missing": sorted(hard_required - hosp_equip),
        }

    needed      = hard_required | set(reqs["critical_equipment"])
    matched     = needed & hosp_equip
    equip_score = (len(matched) / max(len(needed), 1)) * 25 if needed else 25
    breakdown["equipment"]         = round(equip_score, 2)
    breakdown["equipment_matched"] = sorted(matched)
    breakdown["equipment_missing"] = sorted(needed - hosp_equip)

    # 4. Load penalty (0–20 pts, lower load = more pts)  [was 10 — doubled to reduce hub gravity]
    load          = hospital.get("hospital_load", 0.5)
    load_score    = (1 - load) * 20
    breakdown["load"] = round(load_score, 2)

    # 5. ICU match (0–10 pts)
    icu_score = 0.0
    if reqs["min_icu_beds"] > 0:
        if hospital.get("has_icu") and hospital.get("icu_beds", 0) >= reqs["min_icu_beds"]:
            icu_score = 10.0
        elif hospital.get("has_icu"):
            icu_score = 5.0
    breakdown["icu"] = round(icu_score, 2)

    # 6. Severity multiplier
    severity_multiplier = 1 + ((severity_score - 5) / 10) * (reqs["severity_weight"] - 1)
    total = (availability_score + distance_score + equip_score + load_score + icu_score)
    total *= max(0.8, min(severity_multiplier, 1.4))
    breakdown["severity_multiplier"] = round(severity_multiplier, 3)

    return round(total, 2), breakdown


def select_best_hospital(
    hospitals: list[dict],
    ambulance_lat: float,
    ambulance_lng: float,
    condition_type: str,
    severity_score: int,
    required_equipment: list[str],
) -> dict | None:
    """Score all hospitals, return the best one (with score + breakdown attached)."""
    best = None
    best_score = -1.0
    for h in hospitals:
        score, breakdown = score_hospital(
            h, ambulance_lat, ambulance_lng,
            condition_type, severity_score, required_equipment,
        )
        h = {**h, "score": score, "score_breakdown": breakdown}
        if score > best_score:
            best_score = score
            best = h
    return best
