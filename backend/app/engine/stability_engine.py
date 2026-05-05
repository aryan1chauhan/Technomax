from __future__ import annotations

from typing import Any, Mapping

# Baseline survivability windows by condition (minutes).
_BASE_SURVIVAL_MINUTES: dict[str, float] = {
    "cardiac": 55.0,
    "stroke": 70.0,
    "trauma": 60.0,
    "respiratory": 65.0,
    "general": 90.0,
}


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def normalize_condition_type(condition_type: Any) -> str:
    text = str(condition_type or "").strip().lower()
    aliases = {
        "cardiac_arrest": "cardiac",
        "heart_attack": "cardiac",
        "respiratory_distress": "respiratory",
        "head_injury": "trauma",
        "severe_bleeding": "trauma",
        "multi_trauma": "trauma",
    }
    if text in _BASE_SURVIVAL_MINUTES:
        return text
    return aliases.get(text, "general")


def normalize_severity_score(severity_score: Any) -> int:
    if isinstance(severity_score, bool):
        return 5
    if isinstance(severity_score, (int, float)):
        return int(clamp(float(severity_score), 1.0, 10.0))

    text = str(severity_score or "").strip().lower()
    if text.isdigit():
        return int(clamp(float(text), 1.0, 10.0))

    labels = {
        "low": 3,
        "minor": 3,
        "moderate": 6,
        "medium": 6,
        "high": 8,
        "critical": 9,
    }
    return labels.get(text, 5)


def parse_systolic_bp(bp_value: Any) -> float | None:
    if bp_value is None:
        return None

    if isinstance(bp_value, Mapping):
        if "systolic" in bp_value:
            try:
                return float(bp_value["systolic"])
            except (TypeError, ValueError):
                return None
        return None

    if isinstance(bp_value, (tuple, list)) and bp_value:
        try:
            return float(bp_value[0])
        except (TypeError, ValueError):
            return None

    text = str(bp_value).strip()
    if not text:
        return None
    try:
        if "/" in text:
            return float(text.split("/", 1)[0])
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def calculate_vitals_risk(vitals: Mapping[str, Any] | None) -> float:
    if not vitals:
        return 0.0

    risk = 0.0

    oxygen = _to_float(vitals.get("oxygen"))
    if oxygen is not None:
        if oxygen < 85:
            risk += 0.55
        elif oxygen < 90:
            risk += 0.35
        elif oxygen < 94:
            risk += 0.15

    pulse = _to_float(vitals.get("pulse"))
    if pulse is not None:
        if pulse < 40 or pulse > 150:
            risk += 0.30
        elif pulse < 50 or pulse > 130:
            risk += 0.18

    systolic = parse_systolic_bp(vitals.get("bp"))
    if systolic is not None:
        if systolic < 80:
            risk += 0.45
        elif systolic < 90:
            risk += 0.25

    return clamp(risk, 0.0, 1.0)


def calculate_equipment_risk(condition_type: str, ambulance_data: Mapping[str, Any] | None) -> float:
    ambulance_data = ambulance_data or {}

    equipment_weights = {
        "has_oxygen": 0.30,
        "has_ventilator": 0.35,
        "has_defibrillator": 0.35,
    }

    condition_required: dict[str, tuple[str, ...]] = {
        "cardiac": ("has_defibrillator", "has_oxygen"),
        "respiratory": ("has_oxygen", "has_ventilator"),
        "stroke": ("has_oxygen",),
        "trauma": ("has_oxygen",),
        "general": ("has_oxygen",),
    }

    required = condition_required.get(condition_type, condition_required["general"])

    missing_weight = 0.0
    for key in required:
        if not bool(ambulance_data.get(key)):
            missing_weight += equipment_weights[key]

    return clamp(missing_weight, 0.0, 1.0)


def estimate_survival_time(
    severity_score: int,
    condition_type: str,
    equipment_risk: float,
    vitals_risk: float,
) -> float:
    severity_norm = (severity_score - 1) / 9.0
    baseline = _BASE_SURVIVAL_MINUTES.get(condition_type, _BASE_SURVIVAL_MINUTES["general"])

    # Weighted formula combining severity and situational penalties.
    survival = baseline * (1.0 - 0.65 * severity_norm)
    survival -= 40.0 * equipment_risk
    survival -= 25.0 * vitals_risk

    if severity_score > 7:
        survival -= (severity_score - 7) * 6.0

    return round(max(1.0, survival), 2)


def evaluate_stability(
    case_data: Mapping[str, Any] | None,
    ambulance_data: Mapping[str, Any] | None,
    eta_to_best_hospital: Any,
) -> dict[str, Any]:
    case_data = case_data or {}
    ambulance_data = ambulance_data or {}

    severity_score = normalize_severity_score(case_data.get("severity_score"))
    condition_type = normalize_condition_type(case_data.get("condition_type"))
    vitals = case_data.get("vitals") if isinstance(case_data.get("vitals"), Mapping) else None

    eta_minutes = _to_float(eta_to_best_hospital)
    eta_minutes = max(0.1, eta_minutes if eta_minutes is not None else 0.1)

    equipment_risk = calculate_equipment_risk(condition_type, ambulance_data)
    vitals_risk = calculate_vitals_risk(vitals)

    severity_norm = (severity_score - 1) / 9.0
    weighted_risk = (0.55 * severity_norm) + (0.30 * equipment_risk) + (0.15 * vitals_risk)
    stability_score = round(clamp(1.0 - weighted_risk, 0.0, 1.0), 4)

    estimated_survival_time = estimate_survival_time(
        severity_score=severity_score,
        condition_type=condition_type,
        equipment_risk=equipment_risk,
        vitals_risk=vitals_risk,
    )

    stabilization_required = estimated_survival_time < eta_minutes

    return {
        "stability_score": stability_score,
        "estimated_survival_time": estimated_survival_time,
        "stabilization_required": stabilization_required,
    }


__all__ = [
    "clamp",
    "normalize_condition_type",
    "normalize_severity_score",
    "parse_systolic_bp",
    "calculate_vitals_risk",
    "calculate_equipment_risk",
    "estimate_survival_time",
    "evaluate_stability",
]
