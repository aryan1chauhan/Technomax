"""Failure taxonomy for trust pipeline with no generic bucket."""

from __future__ import annotations

from typing import Any


FAILURE_CATEGORIES = [
    "survival_failure",
    "treatment_mismatch",
    "equipment_failure",
    "eta_failure",
    "severe_delay",
    "ambulance_misuse",
    "specialty_miss",
    "input_conflict",
    "handled_conflict",
]


def _stable_vitals(vitals: dict[str, Any]) -> bool:
    oxygen = vitals.get("oxygen")
    pulse = vitals.get("pulse")
    bp = vitals.get("bp")

    oxygen_ok = oxygen is None or float(oxygen) >= 94.0
    pulse_ok = pulse is None or (60.0 <= float(pulse) <= 100.0)

    bp_val = None
    if isinstance(bp, str) and "/" in bp:
        try:
            bp_val = float(bp.split("/")[0])
        except (TypeError, ValueError, IndexError):
            bp_val = None
    elif isinstance(bp, (int, float)):
        bp_val = float(bp)
    bp_ok = bp_val is None or bp_val >= 100.0

    return oxygen_ok and pulse_ok and bp_ok


def classify_failure(
    *,
    result: dict[str, Any],
    breakdown: dict[str, float],
    case: Any,
    primary_hospital: dict[str, Any],
) -> str:
    """Classify every failed decision into one of the required categories."""
    s_survival = float(breakdown.get("S_survival", 1.0))
    s_treatment = float(breakdown.get("S_treatment", 1.0))
    s_equipment = float(breakdown.get("S_equipment", 1.0))
    s_eta = float(breakdown.get("S_eta", 1.0))
    decision_quality_score = _extract_decision_quality_score(result=result, breakdown=breakdown)

    if s_survival < 0.3:
        return "survival_failure"
    if s_treatment < 0.4:
        return "treatment_mismatch"
    if s_equipment < 0.5:
        return "equipment_failure"
    if s_eta < 0.3:
        return "eta_failure"

    reasoning = result.get("reasoning", {})
    eta = float((result.get("primary_destination") or {}).get("eta_minutes", 9999.0))
    survival_time = float(reasoning.get("estimated_survival_time", 0.0))
    if (eta - survival_time) > 5.0:
        return "severe_delay"

    ambulance_equipment = {str(e).lower() for e in getattr(case, "ambulance_equipment", [])}
    required = {str(e).lower() for e in getattr(case, "required_equipment", [])}
    primary_eq = {str(e).lower() for e in primary_hospital.get("equipment", [])}
    if (required & ambulance_equipment) and not (required & primary_eq):
        return "ambulance_misuse"

    condition = str(getattr(case, "condition", "")).lower()
    specialty_map = {
        "stroke": {"neurology", "stroke_unit", "stroke_center"},
        "cardiac": {"cardiology", "cath_lab", "defibrillator"},
        "cardiac_arrest": {"cardiology", "cath_lab", "defibrillator"},
        "heart_attack": {"cardiology", "cath_lab", "defibrillator"},
        "trauma": {"trauma_center", "surgery", "blood_bank"},
        "respiratory": {"ventilator", "respiratory", "oxygen"},
        "respiratory_distress": {"ventilator", "respiratory", "oxygen"},
    }
    expected_specialty = specialty_map.get(condition, set())
    if expected_specialty and not (expected_specialty & primary_eq):
        return "specialty_miss"

    severity = float(getattr(case, "severity_score", getattr(case, "severity", 5.0)))
    vitals = getattr(case, "patient_vitals", getattr(case, "vitals", {})) or {}
    conflicting_signals = (severity >= 8.0 and _stable_vitals(vitals)) or (
        severity <= 3.0 and float(vitals.get("oxygen", 95.0) or 95.0) < 85.0
    )
    if conflicting_signals:
        if decision_quality_score < 0.5:
            return "input_conflict"
        return "handled_conflict"

    # Required by spec: no generic 'other' bucket. Route residuals into input_conflict.
    return "input_conflict"


def _extract_decision_quality_score(*, result: dict[str, Any], breakdown: dict[str, float]) -> float:
    """Best-effort extraction of decision quality for conflict handling classification."""
    direct_quality = result.get("decision_quality_score")
    if isinstance(direct_quality, (int, float)):
        return float(direct_quality)

    reasoning = result.get("reasoning", {}) or {}
    reasoning_quality = reasoning.get("decision_quality_score")
    if isinstance(reasoning_quality, (int, float)):
        return float(reasoning_quality)

    ranked = result.get("ranked_candidates") or []
    if ranked:
        candidate_score = ranked[0].get("score")
        if isinstance(candidate_score, (int, float)):
            return float(candidate_score)

    ml_score = reasoning.get("ml_score")
    if isinstance(ml_score, (int, float)):
        return float(ml_score)

    weighted_breakdown = (
        0.30 * float(breakdown.get("S_survival", 0.0))
        + 0.25 * float(breakdown.get("S_treatment", 0.0))
        + 0.20 * float(breakdown.get("S_equipment", 0.0))
        + 0.15 * float(breakdown.get("S_eta", 0.0))
        + 0.10 * float(breakdown.get("S_load", 0.0))
    )
    if weighted_breakdown > 0.0:
        return weighted_breakdown

    return 0.0
