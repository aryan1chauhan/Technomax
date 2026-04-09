"""
ml_scorer.py — Hybrid Hospital Matchmaking Engine
--------------------------------------------------
Primary path : RandomForest model loaded from ml_training/hospital_model.pkl
Fallback path: Weighted formula (original logic) when pickle is missing/corrupt
"""

import logging
import math
import os
import pickle
import hashlib
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model bootstrap (module-level, one-time load)
# ---------------------------------------------------------------------------

_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "ml_training" / "hospital_model.pkl"
_ml_model = None
_ML_AVAILABLE = False
_MODEL_SHA256 = os.getenv("MODEL_SHA256", "").strip().lower()

try:
    if _MODEL_SHA256:
        digest = hashlib.sha256(_MODEL_PATH.read_bytes()).hexdigest()
        if digest != _MODEL_SHA256:
            raise RuntimeError("Model checksum mismatch")
    with open(_MODEL_PATH, "rb") as f:
        _ml_model = pickle.load(f)
    _ML_AVAILABLE = True
    logger.info("ML model loaded successfully from %s", _MODEL_PATH)
except FileNotFoundError:
    logger.warning(
        "hospital_model.pkl not found at %s — falling back to weighted formula.", _MODEL_PATH
    )
except Exception as exc:  # version mismatch, corrupt file, etc.
    logger.warning(
        "Failed to load hospital_model.pkl (%s: %s) — falling back to weighted formula.",
        type(exc).__name__,
        exc,
    )

# ---------------------------------------------------------------------------
# Severity constants (must mirror generate_dataset.py)
# ---------------------------------------------------------------------------

CONDITION_SEVERITY_MAP: dict[str, int] = {
    # severity 1 — low
    "minor_injury": 1,
    "fever": 1,
    "fracture": 1,
    # severity 2 — moderate
    "stroke": 2,
    "heart_attack": 2,
    "respiratory_distress": 2,
    "severe_bleeding": 2,
    # severity 3 — critical
    "cardiac_arrest": 3,
    "multi_trauma": 3,
    "head_injury": 3,
    "poisoning": 3,
}

EQUIPMENT_FLAGS = [
    "has_ventilator",
    "has_defibrillator",
    "has_ct_scan",
    "has_blood_bank",
    "has_icu_equipment",
]

# Equipment keyword → flag name
_EQUIP_KEY_MAP = {
    "ventilator": "has_ventilator",
    "defibrillator": "has_defibrillator",
    "ct_scan": "has_ct_scan",
    "blood_bank": "has_blood_bank",
    "icu": "has_icu_equipment",
}

# Canonical feature order used during model training
_FEATURE_COLUMNS = [
    "distance_km_norm",
    "beds_norm",
    "icu_norm",
    "equipment_match",
    "severity_weight",
    "has_ventilator",
    "has_defibrillator",
    "has_ct_scan",
    "has_blood_bank",
    "has_icu_equipment",
    "accepting",
    "specialist_present",
    "hospital_load",
    "condition_severity",
    "ot_available",
]

# ---------------------------------------------------------------------------
# Normalisation helpers (must be identical to generate_dataset.py)
# ---------------------------------------------------------------------------


def normalize_distance(km: float) -> float:
    """Inverse decay — closer = higher score."""
    return 1.0 / (1.0 + km * 0.1)


def log_normalize_beds(beds: int) -> float:
    """Log-normalise against the max observed bed count (502)."""
    return math.log1p(beds) / math.log1p(502)


def normalize_icu(icu: int) -> float:
    """Cap at 50 ICU beds."""
    return min(icu / 50.0, 1.0)


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Feature vector builder
# ---------------------------------------------------------------------------


def _build_feature_vector(
    distance_km: float,
    available_beds: int,
    icu_beds: int,
    hospital_equipment: list[str],
    required_equipment: list[str],
    condition: str,
    accepting: bool,
    specialist_count: int,
) -> list[float]:
    """
    Build the feature vector in the exact order the model was trained on.
    Unknown / unavailable features (hospital_load, ot_available) default to 0,
    consistent with training-time defaults.
    """
    condition_severity = CONDITION_SEVERITY_MAP.get(condition, 1)
    severity_weight = condition_severity / 3.0

    # Equipment flags — binary
    hosp_equip_set = {e.lower() for e in hospital_equipment}
    equip_flags = {flag: 0 for flag in EQUIPMENT_FLAGS}
    for keyword, flag in _EQUIP_KEY_MAP.items():
        if keyword in hosp_equip_set:
            equip_flags[flag] = 1

    # Equipment match ratio
    if required_equipment:
        req_set = {e.lower() for e in required_equipment}
        matched = len(req_set & hosp_equip_set)
        equipment_match = matched / len(req_set)
    else:
        equipment_match = 1.0

    # Specialist present — binary
    specialist_present = 1 if specialist_count > 0 else 0

    return [
        normalize_distance(distance_km),           # distance_km_norm
        log_normalize_beds(available_beds),         # beds_norm
        normalize_icu(icu_beds),                    # icu_norm
        equipment_match,                            # equipment_match
        severity_weight,                            # severity_weight
        equip_flags["has_ventilator"],              # has_ventilator
        equip_flags["has_defibrillator"],           # has_defibrillator
        equip_flags["has_ct_scan"],                 # has_ct_scan
        equip_flags["has_blood_bank"],              # has_blood_bank
        equip_flags["has_icu_equipment"],           # has_icu_equipment
        1 if accepting else 0,                      # accepting
        specialist_present,                         # specialist_present
        0,                                          # hospital_load (not tracked live)
        condition_severity,                         # condition_severity
        0,                                          # ot_available (not in Availability model)
    ]


# ---------------------------------------------------------------------------
# Fallback weighted scorer (original logic — kept intact)
# ---------------------------------------------------------------------------


def _weighted_score(
    distance_km: float,
    available_beds: int,
    icu_beds: int,
    hospital_equipment: list[str],
    required_equipment: list[str],
    condition: str,
) -> float:
    dist_score = normalize_distance(distance_km)
    bed_score = log_normalize_beds(available_beds)
    icu_score = normalize_icu(icu_beds)

    hosp_equip_set = {e.lower() for e in hospital_equipment}
    if required_equipment:
        req_set = {e.lower() for e in required_equipment}
        equip_score = len(req_set & hosp_equip_set) / len(req_set)
    else:
        equip_score = 1.0

    condition_severity = CONDITION_SEVERITY_MAP.get(condition, 1)
    severity_weight = condition_severity / 3.0

    # Weighted sum — distance carries the heaviest weight
    return (
        dist_score  * 0.40
        + bed_score * 0.20
        + icu_score * 0.15
        + equip_score * 0.15
        + severity_weight * 0.10
    )


# ---------------------------------------------------------------------------
# Public scoring API
# ---------------------------------------------------------------------------


def score_hospital(
    *,
    ambulance_lat: float,
    ambulance_lon: float,
    hospital_lat: float,
    hospital_lon: float,
    available_beds: int,
    icu_beds: int,
    hospital_equipment: list[str],
    required_equipment: list[str],
    condition: str,
    accepting: bool = True,
    specialist_count: int = 0,
) -> dict[str, Any]:
    """
    Return a score dict for a single hospital candidate.

    Keys always present (guarantees UI / Result.jsx contract):
        score        : float 0–1  (ML confidence or weighted formula)
        ml_used      : bool       (True = RF model, False = fallback formula)
        score_breakdown: dict     (transparency / pros-cons)
        explanation  : str
    """
    distance_km = haversine_km(
        ambulance_lat, ambulance_lon, hospital_lat, hospital_lon
    )
    condition_severity = CONDITION_SEVERITY_MAP.get(condition, 1)

    # ---- Build breakdown (always present for transparency) ----------------
    hosp_equip_set = {e.lower() for e in hospital_equipment}
    req_set = {e.lower() for e in required_equipment} if required_equipment else set()
    matched_equip = req_set & hosp_equip_set
    missing_equip = req_set - hosp_equip_set

    score_breakdown = {
        "distance_km": round(distance_km, 2),
        "distance_score": round(normalize_distance(distance_km), 4),
        "bed_score": round(log_normalize_beds(available_beds), 4),
        "icu_score": round(normalize_icu(icu_beds), 4),
        "equipment_match": round(len(matched_equip) / len(req_set), 4) if req_set else 1.0,
        "condition_severity": condition_severity,
        "severity_weight": round(condition_severity / 3.0, 4),
        "available_beds": available_beds,
        "icu_beds": icu_beds,
        "matched_equipment": sorted(matched_equip),
        "missing_equipment": sorted(missing_equip),
        "accepting": accepting,
        "specialist_present": specialist_count > 0,
    }

    # ---- Score via ML model or fallback -----------------------------------
    if _ML_AVAILABLE:
        try:
            features = _build_feature_vector(
                distance_km=distance_km,
                available_beds=available_beds,
                icu_beds=icu_beds,
                hospital_equipment=hospital_equipment,
                required_equipment=required_equipment,
                condition=condition,
                accepting=accepting,
                specialist_count=specialist_count,
            )
            X = np.array([features], dtype=np.float32)
            # predict_proba returns [[p_class0, p_class1]]
            ml_confidence = float(_ml_model.predict_proba(X)[0, 1])
            score = ml_confidence
            ml_used = True
            score_breakdown["ml_confidence"] = round(ml_confidence, 4)
        except Exception as exc:
            logger.warning("ML predict failed (%s) — using weighted formula.", exc)
            score = _weighted_score(
                distance_km, available_beds, icu_beds,
                hospital_equipment, required_equipment, condition
            )
            ml_used = False
    else:
        score = _weighted_score(
            distance_km, available_beds, icu_beds,
            hospital_equipment, required_equipment, condition
        )
        ml_used = False

    score_breakdown["final_score"] = round(score, 4)
    score_breakdown["ml_used"] = ml_used

    # ---- Human-readable explanation ---------------------------------------
    pros: list[str] = []
    cons: list[str] = []

    if distance_km <= 5:
        pros.append(f"Very close ({distance_km:.1f} km)")
    elif distance_km <= 15:
        pros.append(f"Nearby ({distance_km:.1f} km)")
    else:
        cons.append(f"Relatively far ({distance_km:.1f} km)")

    if available_beds >= 10:
        pros.append(f"{available_beds} beds available")
    elif available_beds > 0:
        cons.append(f"Only {available_beds} beds available")
    else:
        cons.append("No beds available")

    if icu_beds >= 5:
        pros.append(f"{icu_beds} ICU beds")
    elif condition_severity >= 2 and icu_beds == 0:
        cons.append("No ICU capacity")

    if matched_equip:
        pros.append(f"Has required equipment: {', '.join(sorted(matched_equip))}")
    if missing_equip:
        cons.append(f"Missing: {', '.join(sorted(missing_equip))}")

    if specialist_count > 0:
        pros.append("Relevant specialist on duty")

    engine_label = "ML (RandomForest)" if ml_used else "weighted formula (fallback)"
    explanation_list = [f"Scored {score:.2%} via {engine_label}."]
    if pros:
        explanation_list.append("Pros: " + "; ".join(pros) + ".")
    if cons:
        explanation_list.append("Cons: " + "; ".join(cons) + ".")

    return {
        "score": score,
        "ml_used": ml_used,
        "score_breakdown": score_breakdown,
        "explanation": " ".join(explanation_list),
        "pros": pros,
        "cons": cons,
    }


def rank_hospitals(
    hospitals: list[dict[str, Any]],
    *,
    ambulance_lat: float,
    ambulance_lon: float,
    required_equipment: list[str],
    condition: str,
) -> list[dict[str, Any]]:
    """
    Score and sort a list of hospital dicts (from the dispatch query).

    Each hospital dict must contain:
        latitude, longitude, available_beds, icu_beds,
        equipment (list[str]), accepting (bool), specialist_count (int, optional)

    Returns the same list enriched with scoring keys, sorted best-first.
    """
    scored = []
    for h in hospitals:
        result = score_hospital(
            ambulance_lat=ambulance_lat,
            ambulance_lon=ambulance_lon,
            hospital_lat=h["latitude"],
            hospital_lon=h["longitude"],
            available_beds=h.get("available_beds", 0),
            icu_beds=h.get("icu_beds", 0),
            hospital_equipment=h.get("equipment", []),
            required_equipment=required_equipment,
            condition=condition,
            accepting=h.get("accepting", True),
            specialist_count=h.get("specialist_count", 0),
        )
        scored.append({**h, **result})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
