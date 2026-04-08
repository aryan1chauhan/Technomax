# app/engine/ml_scorer.py
"""
Transparent weighted hospital scorer.

Replaces the opaque RandomForest + pickle model with a fully interpretable
scoring engine. Every sub-score, weight, and decision is traceable.

Key behaviors:
  - Hard equipment filter: hospitals missing ANY required equipment are rejected
  - Severity-based weight overrides from SEVERITY_CONFIG
  - Returns top-N scored candidates with score_breakdown, explanation, pros, cons
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy.orm import Session
from app.db.models import Case

from app.core.severity import Severity, SEVERITY_CONFIG, get_severity_config


# ── Condition → Severity mapping ─────────────────────────────────────────────

SEVERITY_MAP: dict[str, Severity] = {
    "cardiac arrest":   Severity.CRITICAL,
    "cardiac_arrest":   Severity.CRITICAL,
    "stroke":           Severity.CRITICAL,
    "trauma":           Severity.CRITICAL,
    "severe trauma":    Severity.CRITICAL,
    "head injury":      Severity.CRITICAL,
    "head_injury":      Severity.CRITICAL,
    "internal bleeding": Severity.CRITICAL,
    "internal_bleeding": Severity.CRITICAL,
    "spinal injury":    Severity.CRITICAL,
    "spinal_injury":    Severity.CRITICAL,
    "chest injury":     Severity.CRITICAL,
    "chest_pain":       Severity.CRITICAL,
    "severe bleeding":  Severity.CRITICAL,
    "respiratory":      Severity.CRITICAL,
    "respiratory failure": Severity.CRITICAL,
    "heart failure":    Severity.CRITICAL,
    "heart_failure":    Severity.CRITICAL,
    "drowning":         Severity.CRITICAL,
    "electrocution":    Severity.CRITICAL,

    "burns":            Severity.MODERATE,
    "anaphylaxis":      Severity.MODERATE,
    "kidney failure":   Severity.MODERATE,
    "kidney_failure":   Severity.MODERATE,
    "liver failure":    Severity.MODERATE,
    "liver_failure":    Severity.MODERATE,
    "obstetric":        Severity.MODERATE,
    "pediatric":        Severity.MODERATE,
    "poisoning":        Severity.MODERATE,
    "allergic_reaction": Severity.MODERATE,
    "allergic reaction": Severity.MODERATE,
    "seizure":          Severity.MODERATE,
    "diabetic":         Severity.MODERATE,
    "snake_bite":       Severity.MODERATE,
    "snake bite":       Severity.MODERATE,
    "pelvic injury":    Severity.MODERATE,
    "hypoglycemic crisis": Severity.MODERATE,
    "spinal":           Severity.MODERATE,

    "fracture":         Severity.LOW,
    "fractures":        Severity.LOW,
    "broken bone":      Severity.LOW,
    "soft tissue injury": Severity.LOW,
    "facial injury":    Severity.LOW,
    "eye_injury":       Severity.LOW,
    "psychiatric":      Severity.LOW,
    "psychological trauma": Severity.LOW,
    "general":          Severity.LOW,
    "infection":        Severity.LOW,
}


# ── Condition → Required specialist mapping ──────────────────────────────────

CONDITION_SPECIALIST_MAP: dict[str, list[str]] = {
    "cardiac arrest":       ["cardiologist"],
    "cardiac_arrest":       ["cardiologist"],
    "chest pain":           ["cardiologist"],
    "chest_pain":           ["cardiologist"],
    "heart failure":        ["cardiologist"],
    "heart_failure":        ["cardiologist"],
    "stroke":               ["neurologist"],
    "seizure":              ["neurologist"],
    "head injury":          ["neurologist"],
    "head_injury":          ["neurologist"],
    "spinal injury":        ["orthopedic"],
    "spinal_injury":        ["orthopedic"],
    "fracture":             ["orthopedic"],
    "broken bone":          ["orthopedic"],
    "pelvic injury":        ["orthopedic"],
    "trauma":               ["general_surgeon"],
    "severe trauma":        ["general_surgeon"],
    "internal bleeding":    ["general_surgeon"],
    "internal_bleeding":    ["general_surgeon"],
    "severe bleeding":      ["general_surgeon"],
    "obstetric":            ["gynecologist"],
    "kidney failure":       ["nephrologist"],
    "kidney_failure":       ["nephrologist"],
    "respiratory":          ["pulmonologist"],
    "respiratory failure":  ["pulmonologist"],
    "burns":                ["plastic_surgeon"],
    "pediatric":            ["pediatrician"],
    "diabetic":             ["endocrinologist"],
    "hypoglycemic crisis":  ["endocrinologist"],
    "poisoning":            ["emergency_physician"],
    "anaphylaxis":          ["emergency_physician"],
    "allergic reaction":    ["emergency_physician"],
    "allergic_reaction":    ["emergency_physician"],
    "chest injury":         ["cardiothoracic_surgeon"],
    "liver failure":        ["gastroenterologist"],
    "liver_failure":        ["gastroenterologist"],
}

# ── Condition → Bonus equipment mapping ──────────────────────────────────────

CONDITION_BONUS_EQUIPMENT_MAP: dict[str, list[str]] = {
    "cardiac arrest":       ["ecg", "defibrillator", "oxygen"],
    "cardiac_arrest":       ["ecg", "defibrillator", "oxygen"],
    "stroke":               ["ct_scan", "mri", "oxygen"],
    "trauma":               ["xray", "ct_scan", "blood_bank"],
    "severe trauma":        ["xray", "ct_scan", "blood_bank"],
    "internal bleeding":    ["blood_bank", "ct_scan"],
    "internal_bleeding":    ["blood_bank", "ct_scan"],
    "chest injury":         ["xray", "ct_scan", "oxygen"],
    "chest_pain":           ["ecg", "oxygen"],
    "respiratory":          ["oxygen", "nebulizer", "pulse_oximeter"],
    "respiratory failure":  ["oxygen", "nebulizer", "pulse_oximeter", "ventilator"],
    "heart failure":        ["ecg", "oxygen", "defibrillator"],
    "heart_failure":        ["ecg", "oxygen", "defibrillator"],
    "burns":                ["oxygen", "iv_fluids", "wound_care"],
    "fracture":             ["xray", "plaster"],
    "broken bone":          ["xray", "plaster"],
    "poisoning":            ["oxygen", "iv_fluids", "gastric_lavage"],
    "anaphylaxis":          ["oxygen", "iv_fluids", "epinephrine"],
    "allergic reaction":    ["oxygen", "iv_fluids"],
    "allergic_reaction":    ["oxygen", "iv_fluids"],
}


# ── Scored result dataclass ──────────────────────────────────────────────────

@dataclass
class ScoredHospital:
    hospital_id: int
    name: str
    distance_km: float
    available_beds: int
    score: float
    score_breakdown: dict[str, float]
    explanation: list[str]
    pros: list[str]
    cons: list[str]
    icu_beds: int = 0
    data_source: str = "live"
    last_updated: Optional[str] = None
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None
    address: Optional[str] = None
    eta_minutes: Optional[int] = None


# ── Sub-score functions (public for testing) ─────────────────────────────────

def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _distance_score(distance_km: float, max_distance_km: float) -> float:
    """Exponential normalized decay: 1.0 at 0 km, dropping heavily over distance."""
    if distance_km >= max_distance_km or max_distance_km <= 0:
        return 0.0
    normalized = distance_km / max_distance_km
    return math.exp(-3.0 * normalized)


BED_CAP = 50  # Beds beyond this don't add more benefit

def _beds_score(beds: int, icu_beds: int = 0, severity: Severity = Severity.MODERATE) -> float:
    """Linear 0-1 score: proportional to beds, capped at BED_CAP. Bonus for ICU in critical cases."""
    base = min(1.0, max(0, beds) / BED_CAP)
    if severity == Severity.CRITICAL and icu_beds > 0:
        icu_bonus = min(0.5, icu_beds * 0.15)
        return min(1.0, base + icu_bonus)
    return base


def _specialist_score(
    hospital_specialists: list[str],
    required_specialists: list[str],
) -> float:
    """Ratio of required specialists that the hospital has. Falls back to doctor count."""
    if not required_specialists:
        return min(1.0, len(hospital_specialists) / 20.0)
    h_specs = {s.lower() for s in hospital_specialists}
    matched = sum(1 for s in required_specialists if s.lower() in h_specs)
    return matched / len(required_specialists)

def _equipment_score(h_equip: set, req_equip: set, bonus_equip: list) -> float:
    """Scores 0.6 for passing hard reqs, boosts up to 1.0 for bonus equipment."""
    bonus = sum(0.1 for e in bonus_equip if e in h_equip)
    return min(1.0, 0.6 + bonus)


def _eta(distance_km: float, speed_kmh: float = 40.0) -> int:
    """Estimated time of arrival in minutes. Minimum 1 minute."""
    return max(1, round(distance_km / speed_kmh * 60))


def _outcome_score(hospital_id: int, condition: str, db: Optional[Session]) -> float:
    """
    Returns 0.5–1.0 based on historical success rate.
    Uses 0.85 as a floor threshold for cold-starts (<5 cases).
    """
    if db is None:
        return 1.0
        
    outcomes = db.query(Case).filter(
        Case.assigned_hospital_id == hospital_id,
        Case.condition == condition,
        Case.status == "completed"
    ).all()
    
    if len(outcomes) < 5:
        return 0.85
        
    success = sum(1 for c in outcomes if c.eta_minutes is not None and c.eta_minutes < 20)
    return 0.5 + 0.5 * (success / len(outcomes))


# ── Main scoring function ───────────────────────────────────────────────────

def score_hospitals(
    hospitals: list[dict],
    condition: str,
    required_equipment: list[str],
    ambulance_lat: float,
    ambulance_lng: float,
    severity_override: str | None = None,
    top_n: int = 3,
    db: Optional[Session] = None,
) -> tuple[list[ScoredHospital], dict]:
    """
    Score and rank hospitals for a dispatch.

    Returns:
        (ranked_list, rejection_summary)

    ranked_list: Top-N ScoredHospital instances, sorted by score descending.
    rejection_summary: Dict with counts of rejected hospitals by reason.
    """
    # Resolve severity
    condition_clean = condition.lower().replace("_", " ")
    if severity_override:
        severity = Severity(severity_override.lower())
    else:
        severity = SEVERITY_MAP.get(condition_clean, Severity.MODERATE)

    config = get_severity_config(severity.value)
    weights = config["weights"]
    min_beds = config["min_beds"]
    max_dist = config["max_distance_km"]

    # Resolve required specialists for this condition
    required_specialists = CONDITION_SPECIALIST_MAP.get(condition_clean, [])

    # ── Equipment name normalization ──
    # Frontend uses "icu_equipment", seed data uses "icu". This alias map
    # ensures both resolve to the same canonical name.
    _EQUIP_ALIASES = {
        "icu_equipment": "icu",
        "icu_equip":     "icu",
        "cardiac_mon":   "cardiac_monitor",
        "ct":            "ct_scan",
        "xray_machine":  "xray",
        "x_ray":         "xray",
    }

    def _normalize_equip(name: str) -> str:
        n = name.lower().strip()
        return _EQUIP_ALIASES.get(n, n)

    # Required equipment as normalized lowercase set
    req_equip_lower = {_normalize_equip(e) for e in required_equipment} if required_equipment else set()

    # Rejection counters
    rejected_equipment = 0
    rejected_beds = 0
    rejected_distance = 0
    total_evaluated = len(hospitals)

    scored: list[ScoredHospital] = []

    import logging
    logging.getLogger(__name__).info(
        "Scoring %d hospitals for condition=%s severity=%s",
        len(hospitals), condition, severity.value
    )

    for h in hospitals:
        h_id = h.get("id", 0)
        h_name = h.get("name", "Unknown")
        h_lat = float(h.get("latitude", h.get("lat", 0)))
        h_lng = float(h.get("longitude", h.get("lng", 0)))
        h_beds = int(h.get("available_beds", h.get("beds", 0)))
        h_icu = int(h.get("icu_beds", h.get("icu", 0)))
        h_equip = {_normalize_equip(e) for e in (h.get("equipment") or [])}
        h_specialists_raw = h.get("specialists") or []
        h_address = h.get("address")
        h_data_source = h.get("data_source", "live")
        h_last_updated = h.get("last_updated")

        # Normalize specialists: handle both dict and list
        if isinstance(h_specialists_raw, dict):
            h_specialists = [k for k, v in h_specialists_raw.items() if v and v > 0]
        elif isinstance(h_specialists_raw, list):
            h_specialists = h_specialists_raw
        else:
            h_specialists = []

        # ── Hard filter 1: Equipment ──
        if req_equip_lower and not req_equip_lower.issubset(h_equip):
            rejected_equipment += 1
            continue

        # ── Hard filter 2: Minimum beds ──
        if h_beds < min_beds:
            rejected_beds += 1
            continue

        # ── Hard filter 3: Distance cap ──
        dist = _haversine(ambulance_lat, ambulance_lng, h_lat, h_lng)
        dist = round(dist, 2)
        if dist > max_dist:
            rejected_distance += 1
            continue

        # ── Sub-scores ──
        d_score = _distance_score(dist, max_dist)
        b_score = _beds_score(h_beds, h_icu, severity)
        s_score = _specialist_score(h_specialists, required_specialists)
        
        # Calculate equipment bonus
        bonus_equip = CONDITION_BONUS_EQUIPMENT_MAP.get(condition_clean, [])
        e_score = _equipment_score(h_equip, req_equip_lower, bonus_equip)

        o_score = _outcome_score(h_id, condition, db)

        # ── Composite weighted score ──
        composite = (
            weights["distance"]   * d_score +
            weights["beds"]       * b_score +
            weights["specialist"] * s_score +
            weights["equipment"]  * e_score
        )
        
        # Multiply by historic self-tuning outcome score
        composite = composite * o_score
        
        composite = round(min(1.0, max(0.0, composite)), 4)

        breakdown = {
            "distance":   round(d_score, 4),
            "beds":       round(b_score, 4),
            "specialist": round(s_score, 4),
            "equipment":  round(e_score, 4),
            "outcome":    round(o_score, 4),
        }

        eta = _eta(dist)

        # ── Explanation ──
        explanation = _build_explanation(
            h_name, dist, h_beds, h_specialists,
            required_specialists, severity, composite,
        )

        # ── Pros / Cons ──
        pros, cons = _build_pros_cons(
            dist, h_beds, h_specialists, h_equip,
            required_specialists, req_equip_lower,
            max_dist, min_beds,
        )

        scored.append(ScoredHospital(
            hospital_id=h_id,
            name=h_name,
            distance_km=dist,
            available_beds=h_beds,
            icu_beds=h_icu,
            score=composite,
            score_breakdown=breakdown,
            explanation=explanation,
            pros=pros,
            cons=cons,
            data_source=h_data_source,
            last_updated=h_last_updated,
            hospital_lat=h_lat,
            hospital_lng=h_lng,
            address=h_address,
            eta_minutes=eta,
        ))

    # Sort by score descending
    scored.sort(key=lambda s: s.score, reverse=True)

    total_rejected = rejected_equipment + rejected_beds + rejected_distance
    total_passed = len(scored)

    rejection_summary = {
        "missing_equipment": rejected_equipment,
        "insufficient_beds": rejected_beds,
        "too_far": rejected_distance,
        "total_rejected": total_rejected,
        "total_evaluated": total_evaluated,
        "total_passed": total_passed,
    }

    return scored[:top_n], rejection_summary


# ── Helpers ──────────────────────────────────────────────────────────────────

def _build_explanation(
    name: str, dist: float, beds: int,
    h_specialists: list[str], required_specialists: list[str],
    severity: Severity, composite: float,
) -> list[str]:
    """Build human-readable explanation lines."""
    lines = [
        f"{name} scored {round(composite * 100)}% for this {severity.value} dispatch.",
        f"Distance: {dist} km — ETA ~{_eta(dist)} min.",
        f"Capacity: {beds} available beds.",
    ]
    if required_specialists:
        matched = [s for s in required_specialists if s.lower() in {sp.lower() for sp in h_specialists}]
        if matched:
            lines.append(f"Specialist match: {', '.join(s.replace('_', ' ').title() for s in matched)}.")
        else:
            lines.append(f"No {', '.join(s.replace('_', ' ').title() for s in required_specialists)} specialist on record.")
    return lines


def _build_pros_cons(
    dist: float, beds: int,
    h_specialists: list[str], h_equip: set[str],
    required_specialists: list[str], req_equip: set[str],
    max_dist: float, min_beds: int,
) -> tuple[list[str], list[str]]:
    """Build pros/cons lists for a hospital."""
    pros: list[str] = []
    cons: list[str] = []

    # Distance
    if dist <= max_dist * 0.3:
        pros.append(f"Very close ({dist} km)")
    elif dist <= max_dist * 0.6:
        pros.append(f"Moderate distance ({dist} km)")
    else:
        cons.append(f"Far ({dist} km)")

    # Beds
    if beds >= 20:
        pros.append(f"Good capacity ({beds} beds)")
    elif beds >= min_beds:
        cons.append(f"Limited capacity ({beds} beds)")
    else:
        cons.append(f"Low capacity ({beds} beds)")

    # Specialists
    if required_specialists:
        h_spec_lower = {s.lower() for s in h_specialists}
        matched = [s for s in required_specialists if s.lower() in h_spec_lower]
        missing = [s for s in required_specialists if s.lower() not in h_spec_lower]
        if matched:
            pros.append(f"Has {', '.join(s.replace('_', ' ').title() for s in matched)}")
        if missing:
            cons.append(f"Missing {', '.join(s.replace('_', ' ').title() for s in missing)}")

    # Equipment (all matched since we hard-filter, but show it)
    if req_equip:
        pros.append(f"All {len(req_equip)} required equipment available")

    # Ensure at least one pro and con
    if not pros:
        pros.append("Meets minimum criteria")
    if not cons:
        cons.append("No significant concerns")

    return pros, cons
