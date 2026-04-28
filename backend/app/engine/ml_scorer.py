"""
ml_scorer.py — ETA-first hospital scoring with ML + robust fallback.

Primary path:
  - Loaded pickle model (sklearn or XGBoost-compatible inference)

Fallback path:
  - Rule-based weighted scoring when model is unavailable/fails

Compatibility guarantees:
  - Existing call sites continue to work.
  - Legacy keys (score, score_breakdown, explanation, pros, cons) remain present.
  - New keys (hospital_id, ml_score) are added.
"""

import hashlib
import importlib
import io
import json
import logging
import math
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np

logger = logging.getLogger(__name__)

# Default fallback weights (used when ACTIVE_WEIGHTS is unavailable).
# ──────────────────────────────────────────────────────────────────────
_DEFAULT_WEIGHTS: dict[str, float] = {    
    "w_survival": 0.22,
    "w_treatment": 0.10,
    "w_equipment": 0.13,
    "w_eta": 0.35,
    "w_load": 0.20,
}

_PRIORITY_TO_WEIGHT_KEYS: dict[str, tuple[str, ...]] = {
    "time": ("w_eta",),
    "specialty": ("w_treatment",),
    "stabilization": ("w_survival",),
    "equipment": ("w_equipment",),
}

_FAILURE_COMPONENT_TO_WEIGHT: dict[str, str] = {
    "eta_delay": "w_eta",
    "late_handover": "w_eta",
    "specialty_mismatch": "w_treatment",
    "treatment_mismatch": "w_treatment",
    "stabilization_miss": "w_survival",
    "stabilization_skip": "w_survival",
    "equipment_gap": "w_equipment",
    "bed_shortage": "w_load",
}

_SCENARIO_ADJUSTMENTS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "learning" / "artifacts" / "scenario_adjustments.json"
)

try:
    # Optional: live-tunable weights for trust-layer optimization.
    from tests.trust_layer import ACTIVE_WEIGHTS as _ACTIVE_WEIGHTS  # type: ignore
except (ImportError, RuntimeError, ValueError, TypeError, OSError):
    _ACTIVE_WEIGHTS = None


def _get_active_weights() -> dict[str, float]:
    """
    Return normalized weight map.

    Uses persisted trust-layer tuning only when learning is enabled. Validation
    and test runs with DISABLE_LEARNING_UPDATE=1 should stay on the default
    baseline so historical tuning data cannot silently skew expectations.
    """
    if os.getenv("DISABLE_LEARNING_UPDATE", "0") == "1":
        source = _DEFAULT_WEIGHTS
    else:
        source = _ACTIVE_WEIGHTS if isinstance(_ACTIVE_WEIGHTS, dict) else _DEFAULT_WEIGHTS
    weights = {
        key: float(source.get(key, _DEFAULT_WEIGHTS[key]))
        for key in _DEFAULT_WEIGHTS
    }
    total = sum(weights.values()) or 1.0
    return {key: value / total for key, value in weights.items()}


def _normalize_weight_map(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, _as_float(weights.get(key), 0.0)) for key in _DEFAULT_WEIGHTS)
    if total <= 0.0:
        return dict(_DEFAULT_WEIGHTS)
    return {
        key: max(0.0, _as_float(weights.get(key), _DEFAULT_WEIGHTS[key])) / total
        for key in _DEFAULT_WEIGHTS
    }


def _load_scenario_adjustments() -> dict[str, Any]:
    cache: dict[str, Any] | None = getattr(_load_scenario_adjustments, "_cache", None)
    cache_mtime: float | None = getattr(_load_scenario_adjustments, "_cache_mtime", None)

    try:
        mtime = _SCENARIO_ADJUSTMENTS_PATH.stat().st_mtime
    except OSError:
        setattr(_load_scenario_adjustments, "_cache", {})
        setattr(_load_scenario_adjustments, "_cache_mtime", None)
        return {}

    if cache is not None and cache_mtime == mtime:
        return cache

    try:
        payload = json.loads(_SCENARIO_ADJUSTMENTS_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            cache = payload
        else:
            cache = {}
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        cache = {}

    setattr(_load_scenario_adjustments, "_cache", cache)
    setattr(_load_scenario_adjustments, "_cache_mtime", mtime)
    return cache


def _scenario_adjusted_weights(
    base_weights: dict[str, float],
    scenario_context: dict[str, Any] | None,
) -> dict[str, float]:
    if not scenario_context:
        return _normalize_weight_map(base_weights)

    adjusted = dict(_normalize_weight_map(base_weights))
    priority_type = str(scenario_context.get("priority_type", "")).strip().lower()
    focus_keys = _PRIORITY_TO_WEIGHT_KEYS.get(priority_type, ())
    # Keep scenario boosts bounded to +/- 20% from base to avoid destabilizing global logic.
    priority_boost = min(0.20, max(0.10, _as_float(scenario_context.get("priority_boost"), 0.15)))

    if focus_keys:
        per_focus = priority_boost / max(1, len(focus_keys))
        non_focus = [key for key in _DEFAULT_WEIGHTS if key not in focus_keys]
        for key in focus_keys:
            adjusted[key] = adjusted.get(key, _DEFAULT_WEIGHTS[key]) + per_focus
        if non_focus:
            reduction = priority_boost / len(non_focus)
            for key in non_focus:
                adjusted[key] = max(0.0, adjusted.get(key, _DEFAULT_WEIGHTS[key]) - reduction)

    # Apply bounded scenario profile multipliers derived from prior simulation runs.
    scenario_name = str(scenario_context.get("scenario_name", "")).strip().lower()
    scenario_profile: dict[str, Any] = {}
    if scenario_name:
        profiles = _load_scenario_adjustments()
        profile = profiles.get(scenario_name)
        if isinstance(profile, dict):
            scenario_profile = profile

    multipliers = scenario_profile.get("weight_multipliers")
    if isinstance(multipliers, dict):
        for key in _DEFAULT_WEIGHTS:
            multiplier = _clamp(_as_float(multipliers.get(key), 1.0), 0.85, 1.15)
            adjusted[key] = adjusted.get(key, _DEFAULT_WEIGHTS[key]) * multiplier

    failure_components = [
        str(item).strip().lower() for item in (scenario_context.get("failure_components") or []) if item
    ]

    # If not explicitly supplied, derive a dominant failure from stored scenario history.
    if not failure_components and isinstance(scenario_profile.get("failure_breakdown"), dict):
        filtered = {
            str(name).strip().lower(): int(value)
            for name, value in scenario_profile.get("failure_breakdown", {}).items()
            if str(name).strip().lower() != "none" and int(_as_float(value, 0.0)) > 0
        }
        if filtered:
            dominant_failure = max(filtered.items(), key=lambda item: item[1])[0]
            failure_components = [dominant_failure]

    # Cap failure-driven feedback to a single +0.05 shift per scenario.
    for component in failure_components[:1]:
        target_key = _FAILURE_COMPONENT_TO_WEIGHT.get(component)
        if target_key:
            adjusted[target_key] = adjusted.get(target_key, _DEFAULT_WEIGHTS[target_key]) + 0.05

    # Under conflicting/corrupted signals, down-weight less reliable dimensions and
    # shift that budget to robustness-oriented components.
    corruption_signals = {
        str(item).strip().lower()
        for item in (scenario_context.get("corruption_signals") or [])
        if item
    }
    conflicting_signals = bool(scenario_context.get("conflicting_signals", False))
    if conflicting_signals or bool(scenario_context.get("input_corruption_detected", False)):
        shift_pool = 0.0

        def _shift_from(key: str, amount: float) -> None:
            nonlocal shift_pool
            current = adjusted.get(key, _DEFAULT_WEIGHTS[key])
            delta = min(amount, max(0.0, current - 0.01))
            adjusted[key] = current - delta
            shift_pool += delta

        if "gps_anomaly" in corruption_signals:
            _shift_from("w_eta", 0.02)
        if "invalid_load_range" in corruption_signals:
            _shift_from("w_load", 0.015)
        if "corrupted_equipment_labels" in corruption_signals:
            _shift_from("w_equipment", 0.02)
        if conflicting_signals and shift_pool <= 0.0:
            _shift_from("w_eta", 0.02)

        if shift_pool > 0.0:
            adjusted["w_survival"] = adjusted.get("w_survival", _DEFAULT_WEIGHTS["w_survival"]) + (shift_pool * 0.70)
            adjusted["w_treatment"] = adjusted.get("w_treatment", _DEFAULT_WEIGHTS["w_treatment"]) + (shift_pool * 0.30)

    if conflicting_signals:
        # Conflict-aware weighting: prefer capability over speed under uncertainty.
        adjusted["w_treatment"] = adjusted.get("w_treatment", _DEFAULT_WEIGHTS["w_treatment"]) * 1.2
        adjusted["w_eta"] = adjusted.get("w_eta", _DEFAULT_WEIGHTS["w_eta"]) * 0.8
        adjusted["w_equipment"] = adjusted.get("w_equipment", _DEFAULT_WEIGHTS["w_equipment"]) * 1.1

    normalized = _normalize_weight_map(adjusted)
    bounded: dict[str, float] = {}
    for key, value in normalized.items():
        base = max(0.0001, _as_float(base_weights.get(key), _DEFAULT_WEIGHTS[key]))
        bounded[key] = _clamp(value, base * 0.8, base * 1.2)
    return _normalize_weight_map(bounded)


def _delay_penalty_multiplier(eta_minutes: float, scenario_context: dict[str, Any] | None) -> float:
    if not scenario_context or not bool(scenario_context.get("survival_critical", False)):
        return 1.0

    eta_threshold = max(1.0, _as_float(scenario_context.get("eta_high_threshold_minutes"), 12.0))
    if eta_minutes <= eta_threshold:
        return 1.0

    overload_ratio = _clamp((eta_minutes - eta_threshold) / eta_threshold, 0.0, 1.0)
    penalty = 0.08 + (0.10 * overload_ratio)
    return _clamp(1.0 - penalty, 0.75, 1.0)


def _uncertainty_risk_penalty_multiplier(
    *,
    uncertainty_high: bool,
    inferred_load: float,
    s_survival: float,
    s_treatment: float,
    s_equipment: float,
    scenario_context: dict[str, Any] | None,
) -> float:
    """Bias toward safer hospitals when uncertainty/conflicts are present."""
    if not uncertainty_high:
        return 1.0

    penalty = 0.0
    if inferred_load >= 0.90:
        penalty += 0.08
    if s_equipment < 0.75:
        penalty += 0.08
    if s_treatment < 0.45:
        penalty += 0.05
    if bool((scenario_context or {}).get("conflicting_signals", False)) and s_survival < 0.70:
        penalty += 0.05

    return _clamp(1.0 - penalty, 0.75, 1.0)


# ---------------------------------------------------------------------------
# Model bootstrap (module-level, one-time load)
# ---------------------------------------------------------------------------

_MODEL_PATH = Path(__file__).resolve().parent.parent.parent / "ml_training" / "hospital_model.pkl"
_ml_model = None
_ML_AVAILABLE = False
_MODEL_SHA256 = os.getenv("MODEL_SHA256", "").strip().lower()
_ML_FALLBACK_WARNING_EMITTED = False
_ML_DISABLED = os.getenv("DISABLE_ML_MODEL", "0") == "1"


def _extract_model(loaded_artifact: Any) -> Any:
    if isinstance(loaded_artifact, dict) and "model" in loaded_artifact:
        return loaded_artifact["model"]
    return loaded_artifact

if not _ML_DISABLED and not _MODEL_SHA256:
    raise RuntimeError(
        "MODEL_SHA256 env var is required for safe model loading. "
        "Set it to the SHA256 hash of the model file."
    )

try:
    if _ML_DISABLED:
        logger.info("ML model disabled by DISABLE_ML_MODEL=1 — using fallback scorer.")
    else:
        with open(_MODEL_PATH, "rb") as f:
            raw = f.read()
        actual_sha = hashlib.sha256(raw).hexdigest()
        if actual_sha != _MODEL_SHA256:
            raise RuntimeError(
                f"Model file integrity check failed. Expected {_MODEL_SHA256}, got {actual_sha}."
            )

        _ml_model = _extract_model(joblib.load(io.BytesIO(raw)))
        _ML_AVAILABLE = True
        logger.info("ML model loaded successfully from %s", _MODEL_PATH)
except FileNotFoundError:
    logger.warning("hospital_model.pkl not found at %s — using fallback scorer.", _MODEL_PATH)
except RuntimeError:
    # Integrity failures must crash startup.
    raise
except (OSError, ValueError) as exc:
    logger.warning(
        "Failed to load hospital_model.pkl (%s: %s) — using fallback scorer.",
        type(exc).__name__,
        exc,
    )


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

CONDITION_SEVERITY_MAP: dict[str, int] = {
    "minor_injury": 1,
    "fever": 1,
    "fracture": 1,
    "stroke": 2,
    "heart_attack": 2,
    "respiratory_distress": 2,
    "severe_bleeding": 2,
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

_EQUIP_KEY_MAP = {
    "ventilator": "has_ventilator",
    "defibrillator": "has_defibrillator",
    "ct_scan": "has_ct_scan",
    "blood_bank": "has_blood_bank",
    "icu": "has_icu_equipment",
}

_TREATMENT_ALIASES: dict[str, set[str]] = {
    "neuro": {"neuro", "neurology", "stroke_unit", "stroke_center"},
    "cardiac": {"cardiac", "cardiology", "cath_lab", "pci"},
    "trauma": {"trauma", "trauma_center", "trauma_care"},
    "respiratory": {"ventilator", "respiratory", "pulmonology"},
}

_SURVIVAL_TAU_BY_CONDITION: dict[str, float] = {
    "stroke": 1.5,
    "cardiac": 2.0,
    "trauma": 2.5,
    "general": 3.0,
}

# Keep legacy order for compatibility with existing trained models.
_FEATURE_COLUMNS = [
    "distance_km_norm",      # now fed by ETA-normalized value for backwards compatibility
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

_EXTENDED_FEATURE_COLUMNS = _FEATURE_COLUMNS + [
    "historical_success_rate_norm",
    "equipment_match_score",
    "icu_availability_norm",
]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def normalize_distance(km: float) -> float:
    """Legacy helper retained for compatibility/tests."""
    km = max(_as_float(km, 0.0), 0.0)
    return 1.0 / (1.0 + km * 0.1)


def normalize_eta(eta_minutes: float) -> float:
    """ETA normalization where lower ETA yields a higher score."""
    eta = max(_as_float(eta_minutes, 0.0), 0.0)
    return 1.0 / (1.0 + eta / 30.0)


def log_normalize_beds(beds: int) -> float:
    beds_int = max(int(_as_float(beds, 0.0)), 0)
    return math.log1p(beds_int) / math.log1p(502)


def normalize_icu(icu: int) -> float:
    icu_int = max(int(_as_float(icu, 0.0)), 0)
    return min(icu_int / 50.0, 1.0)


def normalize_hospital_load(hospital_load: float) -> float:
    return _clamp(_as_float(hospital_load, 0.0), 0.0, 1.0)


def normalize_success_rate(success_rate: float) -> float:
    return _clamp(_as_float(success_rate, 0.65), 0.0, 1.0)


# ---------------------------------------------------------------------------
# Distance/ETA helpers
# ---------------------------------------------------------------------------


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_to_eta_minutes(distance_km: float, avg_speed_kmph: float = 40.0) -> float:
    distance = max(_as_float(distance_km, 0.0), 0.0)
    speed = max(_as_float(avg_speed_kmph, 40.0), 1.0)
    return (distance / speed) * 60.0


# ---------------------------------------------------------------------------
# Feature preparation
# ---------------------------------------------------------------------------


def _equipment_sets(hospital_equipment: list[str], required_equipment: list[str]) -> tuple[set[str], set[str], set[str]]:
    hosp_set = {str(e).strip().lower() for e in (hospital_equipment or []) if e}
    req_set = {str(e).strip().lower() for e in (required_equipment or []) if e}
    matched = req_set & hosp_set
    return hosp_set, req_set, matched


def _normalize_equipment_name(value: str) -> str:
    name = str(value or "").strip().lower()
    aliases = {
        "icu_equipment": "icu",
        "oxygen_cylinder": "oxygen",
        "o2": "oxygen",
        "trauma_care": "trauma_center",
        "ct": "ct_scan",
    }
    return aliases.get(name, name)


def _load_threshold_score(load: float) -> float:
    if load < 0.7:
        return 1.0
    if load < 0.9:
        return 0.5
    return 0.1


def _condition_group(condition: str) -> str:
    cond = str(condition or "").strip().lower()
    if cond in {"stroke"}:
        return "stroke"
    if cond in {"cardiac_arrest", "heart_attack"}:
        return "cardiac"
    if cond in {"multi_trauma", "head_injury", "severe_bleeding", "fracture", "trauma"}:
        return "trauma"
    return "general"


def _is_stabilization_possible(condition: str, effective_equipment: set[str]) -> bool:
    group = _condition_group(condition)
    required_by_group = {
        "stroke": {"oxygen", "ct_scan", "neurology", "stroke_unit"},
        "cardiac": {"oxygen", "defibrillator", "cardiology"},
        "trauma": {"oxygen", "iv", "trauma_center", "surgery"},
        "general": {"oxygen"},
    }
    required = required_by_group.get(group, {"oxygen"})
    return bool(required & effective_equipment)


def _survival_score(
    eta_minutes: float,
    survival_time_minutes: float,
    condition: str,
    stabilization_possible: bool,
) -> float:
    """
    Realistic survival curve with graceful degradation.

    Base:
        S_survival = max(0.2, exp(-max(0, eta - survival_time) / tau(condition)))

    Recovery:
        If stabilization is possible, enforce a recovery floor of 0.3.
    """
    deficit = max(0.0, _as_float(eta_minutes, 0.0) - _as_float(survival_time_minutes, 0.0))
    group = _condition_group(condition)
    tau = max(0.1, _as_float(_SURVIVAL_TAU_BY_CONDITION.get(group, 3.0), 3.0))
    base_survival = max(0.2, math.exp(-(deficit / tau)))
    recovery = 0.3 if stabilization_possible else 0.0
    return _clamp(max(base_survival, recovery), 0.0, 1.0)


def _eta_relative_score(eta_minutes: float, max_eta_minutes: float | None) -> float:
    """Hyperbolic proximity score (closer = higher)."""
    return normalize_eta(eta_minutes)


def _treatment_priority_score(
    condition: str, 
    hospital_equipment_set: set[str], 
    specialist_count: int,
    severity_score: float | None = None
) -> float:
    cond = str(condition or "").strip().lower()
    normalized_equipment = {_normalize_equipment_name(item) for item in hospital_equipment_set}
    
    # Severity-aware dampening: stable cases shouldn't be forced to far hubs
    is_critical = severity_score is not None and severity_score >= 7.0
    base_mismatch = 0.3 if is_critical else 0.90
    
    specialist_bonus = 0.05 if specialist_count > 0 else 0.0

    if cond in {"stroke"}:
        has_target = bool(normalized_equipment & _TREATMENT_ALIASES["neuro"])
        base = 1.0 if has_target else base_mismatch
    elif cond in {"cardiac_arrest", "heart_attack"}:
        has_target = bool(normalized_equipment & _TREATMENT_ALIASES["cardiac"])
        base = 1.0 if has_target else base_mismatch
    elif cond in {"trauma"}:
        has_target = bool(normalized_equipment & _TREATMENT_ALIASES["trauma"])
        base = 1.0 if has_target else base_mismatch
    else:
        base = 0.8  # Default high base for non-specialty conditions

    return _clamp(base + specialist_bonus, 0.0, 1.0)


def _estimate_survival_time_minutes(
    *,
    condition: str,
    severity_score: int,
    ambulance_equipment: set[str],
) -> float:
    cond = str(condition or "").strip().lower()
    baseline_map = {
        "cardiac_arrest": 12.0,
        "heart_attack": 20.0,
        "stroke": 24.0,
        "multi_trauma": 16.0,
        "head_injury": 18.0,
        "severe_bleeding": 16.0,
        "respiratory_distress": 20.0,
        "poisoning": 40.0,
        "fracture": 60.0,
        "fever": 80.0,
        "minor_injury": 90.0,
    }
    baseline = baseline_map.get(cond, 45.0)

    sev = max(1, min(10, int(_as_float(severity_score, 5.0))))
    severity_penalty = (sev - 1) * 2.2

    support_boost = 0.0
    if "oxygen" in ambulance_equipment:
        support_boost += 6.0
    if "ventilator" in ambulance_equipment and cond in {"respiratory_distress", "cardiac_arrest"}:
        support_boost += 8.0
    if "defibrillator" in ambulance_equipment and cond in {"cardiac_arrest", "heart_attack"}:
        support_boost += 8.0

    return max(1.0, baseline - severity_penalty + support_boost)


def _infer_hospital_load(available_beds: int, hospital_load: float | None, total_beds: int | None) -> float:
    if hospital_load is not None:
        return normalize_hospital_load(hospital_load)
    if total_beds and total_beds > 0:
        free_ratio = _clamp(available_beds / float(total_beds), 0.0, 1.0)
        return 1.0 - free_ratio
    return 0.0


def _infer_model_feature_names() -> list[str]:
    # Optimization: Cache the inferred feature names as they don't change until model reload
    cache = getattr(_infer_model_feature_names, "_cache", None)
    if cache is not None:
        return cache

    if not _ML_AVAILABLE or _ml_model is None:
        return list(_FEATURE_COLUMNS)

    names: list[str] | None = None

    model_names = getattr(_ml_model, "feature_names_in_", None)
    if model_names is not None:
        names = [str(name) for name in model_names]

    if names is None and hasattr(_ml_model, "get_booster"):
        try:
            booster = _ml_model.get_booster()
            booster_names = getattr(booster, "feature_names", None)
            if booster_names:
                names = [str(name) for name in booster_names]
        except (AttributeError, TypeError, ValueError, RuntimeError):
            names = None

    if names is None:
        n_features = getattr(_ml_model, "n_features_in_", None)
        if isinstance(n_features, (int, np.integer)):
            n = int(n_features)
            if n <= len(_FEATURE_COLUMNS):
                res = list(_FEATURE_COLUMNS[:n])
                setattr(_infer_model_feature_names, "_cache", res)
                return res
            if n <= len(_EXTENDED_FEATURE_COLUMNS):
                res = list(_EXTENDED_FEATURE_COLUMNS[:n])
                setattr(_infer_model_feature_names, "_cache", res)
                return res
            res = list(_EXTENDED_FEATURE_COLUMNS) + [f"f{i}" for i in range(n - len(_EXTENDED_FEATURE_COLUMNS))]
            setattr(_infer_model_feature_names, "_cache", res)
            return res

    res = names or list(_FEATURE_COLUMNS)
    setattr(_infer_model_feature_names, "_cache", res)
    return res


def _build_feature_vector(
    distance_km: float | None = None,
    eta_minutes: float | None = None,
    available_beds: int = 0,
    icu_beds: int = 0,
    hospital_equipment: list[str] | None = None,
    required_equipment: list[str] | None = None,
    condition: str = "general",
    accepting: bool = True,
    specialist_count: int = 0,
    hospital_load: float | None = None,
    historical_success_rate: float | None = None,
    has_icu: bool | None = None,
    total_beds: int | None = None,
    feature_names: list[str] | None = None,
    equipment_match_override: float | None = None,
) -> list[float]:
    """Build model features with robust defaults and normalized values."""
    available_beds = max(int(_as_float(available_beds, 0.0)), 0)
    icu_beds = max(int(_as_float(icu_beds, 0.0)), 0)
    condition_key = str(condition or "").strip().lower()
    condition_severity = CONDITION_SEVERITY_MAP.get(condition_key, 1)
    severity_weight = condition_severity / 3.0

    eta = _as_float(eta_minutes, -1.0)
    if eta < 0:
        eta = distance_to_eta_minutes(_as_float(distance_km, 0.0))

    hosp_set, req_set, matched = _equipment_sets(hospital_equipment or [], required_equipment or [])
    equipment_match_score = (len(matched) / len(req_set)) if req_set else 1.0
    if equipment_match_override is not None:
        equipment_match_score = _clamp(_as_float(equipment_match_override, equipment_match_score), 0.0, 1.0)

    equip_flags = {flag: 0.0 for flag in EQUIPMENT_FLAGS}
    for keyword, flag in _EQUIP_KEY_MAP.items():
        if keyword in hosp_set:
            equip_flags[flag] = 1.0

    inferred_load = _infer_hospital_load(available_beds, hospital_load, total_beds)
    success_rate = normalize_success_rate(0.65 if historical_success_rate is None else historical_success_rate)
    icu_availability_norm = 1.0 if bool(has_icu) else normalize_icu(icu_beds)

    # Keep legacy field names while feeding ETA-normalized score into first slot.
    feature_map: dict[str, float] = {
        "distance_km_norm": normalize_eta(eta),
        "eta_minutes_norm": normalize_eta(eta),
        "beds_norm": log_normalize_beds(available_beds),
        "icu_norm": icu_availability_norm,
        "equipment_match": equipment_match_score,
        "equipment_match_score": equipment_match_score,
        "severity_weight": severity_weight,
        "has_ventilator": equip_flags["has_ventilator"],
        "has_defibrillator": equip_flags["has_defibrillator"],
        "has_ct_scan": equip_flags["has_ct_scan"],
        "has_blood_bank": equip_flags["has_blood_bank"],
        "has_icu_equipment": equip_flags["has_icu_equipment"],
        "accepting": 1.0 if accepting else 0.0,
        "specialist_present": 1.0 if specialist_count > 0 else 0.0,
        "hospital_load": inferred_load,
        "hospital_load_norm": inferred_load,
        "condition_severity": float(condition_severity),
        "ot_available": 0.0,
        "historical_success_rate": success_rate,
        "historical_success_rate_norm": success_rate,
        "icu_availability": icu_availability_norm,
        "icu_availability_norm": icu_availability_norm,
    }

    selected = feature_names or list(_FEATURE_COLUMNS)
    vector: list[float] = []
    for name in selected:
        value = feature_map.get(name, 0.0)
        if name == "condition_severity":
            vector.append(_clamp(value, 1.0, 3.0))
        else:
            vector.append(_clamp(value, 0.0, 1.0))
    return vector


# ---------------------------------------------------------------------------
# Fallback rule-based scoring
# ---------------------------------------------------------------------------


def _fallback_rule_based_score(
    *,
    eta_minutes: float,
    available_beds: int,
    icu_beds: int,
    hospital_equipment: list[str],
    required_equipment: list[str],
    condition: str,
    accepting: bool,
    specialist_count: int,
    hospital_load: float,
    historical_success_rate: float,
    has_icu: bool,
    equipment_match_score_override: float | None = None,
    ambulance_equipment: list[str] | None = None,
    severity_score: int | None = None,
    max_eta_minutes: float | None = None,
    survival_time_minutes: float | None = None,
    scenario_context: dict[str, Any] | None = None,
) -> float:
    hosp_set, req_set, _ = _equipment_sets(hospital_equipment, required_equipment)
    ambulance_set = {_normalize_equipment_name(item) for item in (ambulance_equipment or []) if item}
    effective_set = {_normalize_equipment_name(item) for item in hosp_set} | ambulance_set
    normalized_required = {_normalize_equipment_name(item) for item in req_set}

    equipment_match_score = (len(normalized_required & effective_set) / len(normalized_required)) if normalized_required else 1.0
    if equipment_match_score_override is not None:
        equipment_match_score = _clamp(_as_float(equipment_match_score_override, equipment_match_score), 0.0, 1.0)

    cond = str(condition or "").strip().lower()
    default_severity = CONDITION_SEVERITY_MAP.get(cond, 1)
    normalized_severity_score = max(1, min(10, int(_as_float(severity_score, default_severity * 3.0))))
    est_survival = (
        _as_float(survival_time_minutes, 0.0)
        if survival_time_minutes is not None
        else _estimate_survival_time_minutes(
            condition=cond,
            severity_score=normalized_severity_score,
            ambulance_equipment=ambulance_set,
        )
    )

    stabilization_possible = _is_stabilization_possible(cond, effective_set)
    s_survival = _survival_score(
        eta_minutes,
        est_survival,
        cond,
        stabilization_possible,
    )
    s_treatment = _treatment_priority_score(
        condition=str(condition or "").strip().lower(),
        hospital_equipment_set=hosp_set,
        specialist_count=specialist_count,
        severity_score=severity_score
    )
    s_equipment = _clamp(equipment_match_score, 0.0, 1.0)
    s_eta = _eta_relative_score(eta_minutes, max_eta_minutes)
    s_load = _load_threshold_score(normalize_hospital_load(hospital_load))

    weights = _scenario_adjusted_weights(_get_active_weights(), scenario_context)
    score = (
        (weights["w_survival"] * s_survival)
        + (weights["w_treatment"] * s_treatment)
        + (weights["w_equipment"] * s_equipment)
        + (weights["w_eta"] * s_eta)
        + (weights["w_load"] * s_load)
    )

    # Additional safety penalties keep obviously poor candidates from clustering
    # near acceptable scores under sparse-data fallback scenarios.
    if available_beds <= 0:
        score -= 0.06
    if normalized_required and s_equipment < 0.5:
        score -= 0.05
    if _as_float(eta_minutes, 0.0) >= 45.0:
        score -= 0.04

    if not accepting:
        score *= 0.60

    return _clamp(score, 0.15, 1.0)


def _weighted_score(
    distance_km: float,
    available_beds: int,
    icu_beds: int,
    hospital_equipment: list[str],
    required_equipment: list[str],
    condition: str,
) -> float:
    """Backward-compatible wrapper used by legacy tests/callers."""
    return _fallback_rule_based_score(
        eta_minutes=distance_to_eta_minutes(distance_km),
        available_beds=available_beds,
        icu_beds=icu_beds,
        hospital_equipment=hospital_equipment,
        required_equipment=required_equipment,
        condition=condition,
        accepting=True,
        specialist_count=0,
        hospital_load=0.0,
        historical_success_rate=0.65,
        has_icu=icu_beds > 0,
        ambulance_equipment=None,
        severity_score=None,
        max_eta_minutes=None,
        survival_time_minutes=None,
    )


# ---------------------------------------------------------------------------
# Model inference helpers (sklearn + XGBoost compatibility)
# ---------------------------------------------------------------------------


def _coerce_probability(value: Any) -> float:
    score = _as_float(value, 0.5)
    if 0.0 <= score <= 1.0:
        return _clamp(score, 0.0, 1.0)
    # Convert logits/raw margins when needed.
    try:
        return 1.0 / (1.0 + math.exp(-score))
    except OverflowError:
        return 1.0 if score > 0 else 0.0


def _predict_ml_scores_batch(feature_vectors: list[list[float]], feature_names: list[str]) -> list[float]:
    if not feature_vectors:
        return []
    if _ml_model is None:
        raise RuntimeError("Model is not loaded")

    X = np.array(feature_vectors, dtype=np.float32)
    errors: list[str] = []
    num_samples = len(feature_vectors)

    if hasattr(_ml_model, "predict_proba"):
        try:
            X_input = X
            if hasattr(_ml_model, "feature_names_in_"):
                try:
                    # Column alignment for model compatibility
                    cols = list(_ml_model.feature_names_in_[: X.shape[1]])
                    X_input = X
                    if len(cols) == X.shape[1]:
                        # Optimized path: if it's a pandas-trained model, we only convert once
                        import pandas as pd  # noqa: PLC0415
                        X_input = pd.DataFrame(X, columns=cols)
                except Exception:  # noqa: BLE001
                    pass
            proba = np.asarray(_ml_model.predict_proba(X_input), dtype=np.float32)
            if proba.ndim == 2 and proba.shape[1] >= 2:
                return [_coerce_probability(p) for p in proba[:, 1]]
            return [_coerce_probability(p) for p in proba.reshape(-1)[:num_samples]]
        except Exception as exc:  # noqa: BLE001
            errors.append(f"predict_proba failed: {exc}")

    if hasattr(_ml_model, "get_booster"):
        try:
            xgb = importlib.import_module("xgboost")
            booster = _ml_model.get_booster()
            dmatrix = xgb.DMatrix(X, feature_names=feature_names[: X.shape[1]])
            pred = booster.predict(dmatrix)
            return [_coerce_probability(p) for p in np.asarray(pred).reshape(-1)[:num_samples]]
        except Exception as exc:  # noqa: BLE001
            errors.append(f"xgboost booster predict failed: {exc}")

    if hasattr(_ml_model, "predict"):
        try:
            pred = np.asarray(_ml_model.predict(X), dtype=np.float32)
            if pred.ndim == 2 and pred.shape[1] >= 2:
                return [_coerce_probability(p) for p in pred[:, 1]]
            return [_coerce_probability(p) for p in pred.reshape(-1)[:num_samples]]
        except Exception as exc:  # noqa: BLE001
            errors.append(f"predict failed: {exc}")

    raise RuntimeError("; ".join(errors) if errors else "No supported prediction API found")


def _predict_ml_score(feature_vector: list[float], feature_names: list[str]) -> float:
    return _predict_ml_scores_batch([feature_vector], feature_names)[0]


# ---------------------------------------------------------------------------
# Public scoring API
# ---------------------------------------------------------------------------


def score_hospital(
    *,
    hospital_id: int | None = None,
    ambulance_lat: float,
    ambulance_lon: float,
    hospital_lat: float,
    hospital_lon: float,
    eta_minutes: float | None = None,
    available_beds: int,
    icu_beds: int,
    hospital_equipment: list[str],
    required_equipment: list[str],
    condition: str,
    accepting: bool = True,
    specialist_count: int = 0,
    hospital_load: float | None = None,
    historical_success_rate: float | None = None,
    has_icu: bool | None = None,
    total_beds: int | None = None,
    equipment_match_override: float | None = None,
    ambulance_equipment: list[str] | None = None,
    severity_score: int | None = None,
    max_eta_minutes: float | None = None,
    survival_time_minutes: float | None = None,
    scenario_context: dict[str, Any] | None = None,
    ml_score_override: float | None = None,
    return_features: bool = False,
    # Optional pre-computed items to save CPU in loops
    pre_adjustments: dict[str, Any] | None = None,
    pre_model_features: list[str] | None = None,
) -> dict[str, Any]:
    """
    Return a robust score payload for a single hospital candidate.

    New keys:
      - hospital_id
      - ml_score

    Legacy keys retained for compatibility:
      - score, ml_used, score_breakdown, explanation, pros, cons
    """
    distance_km = haversine_km(ambulance_lat, ambulance_lon, hospital_lat, hospital_lon)
    eta = _as_float(eta_minutes, -1.0)
    if eta < 0:
        eta = distance_to_eta_minutes(distance_km)

    available_beds = max(int(_as_float(available_beds, 0.0)), 0)
    icu_beds = max(int(_as_float(icu_beds, 0.0)), 0)
    condition_key = str(condition or "").strip().lower()
    condition_severity = CONDITION_SEVERITY_MAP.get(condition_key, 1)

    _, req_set, matched_equip = _equipment_sets(hospital_equipment, required_equipment)
    missing_equip = req_set - matched_equip
    equipment_match_score = (len(matched_equip) / len(req_set)) if req_set else 1.0
    if equipment_match_override is not None:
        equipment_match_score = _clamp(_as_float(equipment_match_override, equipment_match_score), 0.0, 1.0)

    inferred_load = _infer_hospital_load(available_beds, hospital_load, total_beds)
    success_rate = normalize_success_rate(0.65 if historical_success_rate is None else historical_success_rate)
    icu_availability_norm = 1.0 if bool(has_icu) else normalize_icu(icu_beds)

    ambulance_set = {_normalize_equipment_name(item) for item in (ambulance_equipment or []) if item}
    normalized_hospital_set = {_normalize_equipment_name(item) for item in (hospital_equipment or []) if item}
    normalized_required_set = {_normalize_equipment_name(item) for item in req_set}
    effective_equipment_set = normalized_hospital_set | ambulance_set

    stabilization_possible = _is_stabilization_possible(condition_key, effective_equipment_set)
    s_survival = _survival_score(
        eta,
        (
            _as_float(survival_time_minutes, 0.0)
            if survival_time_minutes is not None
            else _estimate_survival_time_minutes(
                condition=condition_key,
                severity_score=max(1, min(10, int(_as_float(severity_score, condition_severity * 3.0)))),
                ambulance_equipment=ambulance_set,
            )
        ),
        condition_key,
        stabilization_possible,
    )
    s_treatment = _treatment_priority_score(
        condition=condition_key,
        hospital_equipment_set=normalized_hospital_set,
        specialist_count=specialist_count,
        severity_score=severity_score
    )
    uncertainty_value = _as_float((scenario_context or {}).get("uncertainty", 0.0), 0.0)
    uncertainty_high = bool((scenario_context or {}).get("uncertainty_high", False)) or (uncertainty_value >= 0.6)
    if uncertainty_high:
        s_treatment = _clamp(s_treatment + 0.10, 0.0, 1.0)
    s_equipment = (
        (len(normalized_required_set & effective_equipment_set) / len(normalized_required_set))
        if normalized_required_set
        else 1.0
    )
    if equipment_match_override is not None:
        s_equipment = _clamp(_as_float(equipment_match_override, s_equipment), 0.0, 1.0)
    s_eta = _eta_relative_score(eta, max_eta_minutes)
    s_load = _load_threshold_score(inferred_load)

    # Optimization: Use pre-loaded adjustments if provided
    adjustments = pre_adjustments if pre_adjustments is not None else _load_scenario_adjustments()
    dynamic_weights = _scenario_adjusted_weights(_get_active_weights(), scenario_context, adjustments=adjustments)
    interpretable_score = _clamp(
        (dynamic_weights["w_survival"] * s_survival)
        + (dynamic_weights["w_treatment"] * s_treatment)
        + (dynamic_weights["w_equipment"] * s_equipment)
        + (dynamic_weights["w_eta"] * s_eta)
        + (dynamic_weights["w_load"] * s_load),
        0.0,
        1.0,
    )

    score_breakdown = {
        "distance_km": round(distance_km, 2),
        "eta_minutes": round(eta, 2),
        "distance_score": round(normalize_eta(eta), 4),
        "eta_score": round(normalize_eta(eta), 4),
        "bed_score": round(log_normalize_beds(available_beds), 4),
        "icu_score": round(icu_availability_norm, 4),
        "icu_availability": round(icu_availability_norm, 4),
        "equipment_match": round(equipment_match_score, 4),
        "equipment_match_score": round(equipment_match_score, 4),
        "historical_success_rate": round(success_rate, 4),
        "hospital_load": round(inferred_load, 4),
        "hospital_load_score": round(1.0 - inferred_load, 4),
        "condition_severity": condition_severity,
        "severity_weight": round(condition_severity / 3.0, 4),
        "available_beds": available_beds,
        "icu_beds": icu_beds,
        "matched_equipment": sorted(matched_equip),
        "missing_equipment": sorted(missing_equip),
        "accepting": bool(accepting),
        "specialist_present": specialist_count > 0,
        "S_survival": round(s_survival, 4),
        "S_treatment": round(s_treatment, 4),
        "S_equipment": round(s_equipment, 4),
        "S_eta": round(s_eta, 4),
        "S_load": round(s_load, 4),
        "interpretable_score": round(interpretable_score, 4),
        "dynamic_weights": {key: round(value, 4) for key, value in dynamic_weights.items()},
        "scenario_priority_type": str((scenario_context or {}).get("priority_type", "")),
        "uncertainty_high": uncertainty_high,
        "conflicting_signals": bool((scenario_context or {}).get("conflicting_signals", False)),
        "ambulance_equipment_used": sorted(ambulance_set),
        "effective_equipment_set": sorted(effective_equipment_set),
    }

    # Optimization: Use pre-computed feature names
    model_features = pre_model_features if pre_model_features is not None else _infer_model_feature_names()
    feature_vector = _build_feature_vector(
        distance_km=distance_km,
        eta_minutes=eta,
        available_beds=available_beds,
        icu_beds=icu_beds,
        hospital_equipment=hospital_equipment,
        required_equipment=required_equipment,
        condition=condition_key,
        accepting=accepting,
        specialist_count=specialist_count,
        hospital_load=inferred_load,
        historical_success_rate=success_rate,
        has_icu=bool(has_icu),
        total_beds=total_beds,
        feature_names=model_features,
        equipment_match_override=equipment_match_score,
    )

    if return_features:
        return {
            "feature_vector": feature_vector,
            "interpretable_score": interpretable_score,
            "score_breakdown": score_breakdown,
            "model_features": model_features,
            "s_survival": s_survival,
            "s_treatment": s_treatment,
            "s_equipment": s_equipment,
            "inferred_load": inferred_load,
            "eta": eta,
            "distance_km": distance_km,
            "available_beds": available_beds,
            "icu_beds": icu_beds,
            "hospital_equipment": hospital_equipment,
            "required_equipment": required_equipment,
            "condition_key": condition_key,
            "accepting": accepting,
            "specialist_count": specialist_count,
            "success_rate": success_rate,
            "has_icu": has_icu,
            "icu_availability_norm": icu_availability_norm,
            "matched_equip": matched_equip,
            "missing_equip": missing_equip,
            "condition_severity": condition_severity,
        }

    ml_used = False
    global _ML_FALLBACK_WARNING_EMITTED

    # Optimization: If we are just finalizing a pre-computed score, skip re-calculation.
    if ml_score_override is not None:
        ml_score = ml_score_override
        ml_used = True
        # For finalizing, we assume score_breakdown was already mostly built in return_features=True call
        # but we need to merge the ML specific bits.
        score_breakdown["ml_confidence"] = round(ml_score, 4)
        return {
            "hospital_id": hospital_id,
            "ml_score": ml_score,
            "score": ml_score,
            "ml_used": True,
            "score_breakdown": score_breakdown,
            "explanation": "Optimized ML-first scoring applied.",
            "pros": ["ML confidence high"],
            "cons": [],
        }

    if _ML_AVAILABLE:
        try:
            ml_score = _predict_ml_score(feature_vector, model_features)
            ml_score = _clamp(ml_score, 0.15, 1.0)
            ml_used = True
            score_breakdown["ml_confidence"] = round(ml_score, 4)
        except (ImportError, AttributeError, TypeError, ValueError, RuntimeError, IndexError) as exc:
            if not _ML_FALLBACK_WARNING_EMITTED:
                logger.warning("ML/XGBoost prediction failed (%s) — using rule-based fallback.", exc)
                _ML_FALLBACK_WARNING_EMITTED = True
            ml_score = _fallback_rule_based_score(
                eta_minutes=eta,
                available_beds=available_beds,
                icu_beds=icu_beds,
                hospital_equipment=hospital_equipment,
                required_equipment=required_equipment,
                condition=condition_key,
                accepting=accepting,
                specialist_count=specialist_count,
                hospital_load=inferred_load,
                historical_success_rate=success_rate,
                has_icu=bool(has_icu),
                equipment_match_score_override=equipment_match_score,
                ambulance_equipment=ambulance_equipment,
                severity_score=severity_score,
                max_eta_minutes=max_eta_minutes,
                survival_time_minutes=survival_time_minutes,
                scenario_context=scenario_context,
            )
    else:
        ml_score = _fallback_rule_based_score(
            eta_minutes=eta,
            available_beds=available_beds,
            icu_beds=icu_beds,
            hospital_equipment=hospital_equipment,
            required_equipment=required_equipment,
            condition=condition_key,
            accepting=accepting,
            specialist_count=specialist_count,
            hospital_load=inferred_load,
            historical_success_rate=success_rate,
            has_icu=bool(has_icu),
            equipment_match_score_override=equipment_match_score,
            ambulance_equipment=ambulance_equipment,
            severity_score=severity_score,
            max_eta_minutes=max_eta_minutes,
            survival_time_minutes=survival_time_minutes,
            scenario_context=scenario_context,
        )

    # Scenario calibration keeps ML ranking explainable while honoring scenario-specific priorities.
    if scenario_context:
        pre_calibration = ml_score
        ml_score = (0.65 * ml_score) + (0.35 * interpretable_score)
        score_breakdown["pre_calibration_ml_score"] = round(pre_calibration, 4)
        score_breakdown["scenario_calibration_applied"] = True

    uncertainty_penalty = _uncertainty_risk_penalty_multiplier(
        uncertainty_high=uncertainty_high,
        inferred_load=inferred_load,
        s_survival=s_survival,
        s_treatment=s_treatment,
        s_equipment=s_equipment,
        scenario_context=scenario_context,
    )
    if uncertainty_penalty < 1.0:
        ml_score *= uncertainty_penalty
        score_breakdown["uncertainty_risk_penalty"] = round(uncertainty_penalty, 4)

    delay_penalty_multiplier = _delay_penalty_multiplier(eta, scenario_context)
    if os.getenv("TRUST_TRACE_SIGNALS", "0") == "1":
        print(
            "SCORER FLAGS:",
            bool((scenario_context or {}).get("conflicting_signals", False)),
            uncertainty_high,
            round(delay_penalty_multiplier, 4),
        )
    if delay_penalty_multiplier < 1.0:
        ml_score *= delay_penalty_multiplier
        score_breakdown["delay_penalty_multiplier"] = round(delay_penalty_multiplier, 4)

    ml_score = _clamp(ml_score, 0.15, 1.0)
    score_breakdown["final_score"] = round(ml_score, 4)
    score_breakdown["ml_used"] = ml_used

    pros: list[str] = []
    cons: list[str] = []

    if eta <= 8:
        pros.append(f"Very close ({distance_km:.1f} km), ETA {eta:.1f} min")
    elif eta <= 20:
        pros.append(f"Nearby ({distance_km:.1f} km), ETA {eta:.1f} min")
    else:
        cons.append(f"Relatively far ({distance_km:.1f} km), slow ETA ({eta:.1f} min)")

    if available_beds >= 10:
        pros.append(f"{available_beds} beds available")
    elif available_beds > 0:
        cons.append(f"Only {available_beds} beds available")
    else:
        cons.append("No beds available")

    if icu_availability_norm > 0:
        pros.append("ICU available")
    elif condition_severity >= 2:
        cons.append("No ICU capacity")

    if matched_equip:
        pros.append(f"Has required equipment: {', '.join(sorted(matched_equip))}")
    if missing_equip:
        cons.append(f"Missing: {', '.join(sorted(missing_equip))}")

    if inferred_load >= 0.85:
        cons.append("High hospital load")
    elif inferred_load <= 0.30:
        pros.append("Low hospital load")

    if success_rate >= 0.80:
        pros.append("Strong historical success rate")
    elif success_rate <= 0.45:
        cons.append("Lower historical success rate")

    if specialist_count > 0:
        pros.append("Relevant specialist on duty")

    engine_label = "ML model" if ml_used else "rule-based fallback"
    explanation_list = [f"Scored {ml_score:.2%} via {engine_label}."]
    if pros:
        explanation_list.append("Pros: " + "; ".join(pros) + ".")
    if cons:
        explanation_list.append("Cons: " + "; ".join(cons) + ".")

    return {
        "hospital_id": hospital_id,
        "ml_score": ml_score,
        # Legacy aliases retained for existing callers.
        "score": ml_score,
        "ml_used": ml_used,
        "score_breakdown": score_breakdown,
        "explanation": " ".join(explanation_list),
        "pros": pros,
        "cons": cons,
    }


async def rank_hospitals(
    hospitals: list[dict[str, Any]],
    *,
    ambulance_lat: float,
    ambulance_lon: float,
    required_equipment: list[str],
    condition: str,
    ambulance_equipment: list[str] | None = None,
    severity_score: int | None = None,
    survival_time_minutes: float | None = None,
    scenario_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Score and sort hospital candidates by ML score (best first)."""
    eta_candidates: list[float] = []
    for hospital in hospitals:
        eta_val = hospital.get("eta_minutes")
        if eta_val is None:
            eta_val = distance_to_eta_minutes(
                haversine_km(
                    ambulance_lat,
                    ambulance_lon,
                    hospital.get("latitude", ambulance_lat),
                    hospital.get("longitude", ambulance_lon),
                )
            )
        eta_candidates.append(max(0.0, _as_float(eta_val, 0.0)))
    max_eta_minutes = max(eta_candidates) if eta_candidates else None

    # Step 1: Extract features and rule-based scores for all hospitals
    prepped: list[dict[str, Any]] = []
    feature_vectors: list[list[float]] = []
    model_features = _infer_model_feature_names()

    # Optimization: Only load scenario adjustments once per rank call
    scenario_adjustments = _load_scenario_adjustments()

    for hospital in hospitals:
        # We pass dummy context if none to ensure consistency
        res = score_hospital(
            hospital_id=hospital.get("id") or hospital.get("hospital_id"),
            ambulance_lat=ambulance_lat,
            ambulance_lon=ambulance_lon,
            hospital_lat=hospital.get("latitude") or hospital.get("lat", ambulance_lat),
            hospital_lon=hospital.get("longitude") or hospital.get("lon", ambulance_lon),
            eta_minutes=hospital.get("eta_minutes"),
            available_beds=hospital.get("available_beds", 0),
            icu_beds=hospital.get("icu_beds", 0),
            hospital_equipment=hospital.get("equipment", []),
            required_equipment=required_equipment,
            condition=condition,
            accepting=hospital.get("accepting", True),
            specialist_count=hospital.get("specialist_count", 0),
            hospital_load=hospital.get("hospital_load"),
            historical_success_rate=hospital.get("historical_success_rate"),
            has_icu=hospital.get("has_ICU"),
            total_beds=hospital.get("total_beds"),
            equipment_match_override=hospital.get("equipment_match_score"),
            ambulance_equipment=ambulance_equipment,
            severity_score=severity_score,
            max_eta_minutes=max_eta_minutes,
            survival_time_minutes=survival_time_minutes,
            scenario_context=scenario_context,
            return_features=True,
            pre_adjustments=scenario_adjustments,
            pre_model_features=model_features,
        )
        prepped.append(res)
        feature_vectors.append(res["feature_vector"])

    # Step 2: Batch predict ML scores
    ml_scores: list[float] = []
    if _ML_AVAILABLE and feature_vectors:
        try:
            import asyncio  # noqa: PLC0415
            ml_scores = await asyncio.to_thread(_predict_ml_scores_batch, feature_vectors, model_features)
        except Exception:  # noqa: BLE001
            ml_scores = [None] * len(feature_vectors)
    else:
        ml_scores = [None] * len(feature_vectors)

    # Step 3: Finalize (Optimized)
    scored: list[dict[str, Any]] = []
    for i, hospital in enumerate(hospitals):
        # We use the 'finalize' shortcut by passing ml_score_override to score_hospital
        # It will detect the override and skip re-calculating features.
        final_res = score_hospital(
            hospital_id=hospital.get("id") or hospital.get("hospital_id"),
            ambulance_lat=ambulance_lat,
            ambulance_lon=ambulance_lon,
            hospital_lat=hospital.get("latitude") or hospital.get("lat", ambulance_lat),
            hospital_lon=hospital.get("longitude") or hospital.get("lon", ambulance_lon),
            eta_minutes=hospital.get("eta_minutes"),
            available_beds=hospital.get("available_beds", 0),
            icu_beds=hospital.get("icu_beds", 0),
            hospital_equipment=hospital.get("equipment", []),
            required_equipment=required_equipment,
            condition=condition,
            accepting=hospital.get("accepting", True),
            specialist_count=hospital.get("specialist_count", 0),
            hospital_load=hospital.get("hospital_load"),
            historical_success_rate=hospital.get("historical_success_rate"),
            has_icu=hospital.get("has_ICU"),
            total_beds=hospital.get("total_beds"),
            equipment_match_override=hospital.get("equipment_match_score"),
            ambulance_equipment=ambulance_equipment,
            severity_score=severity_score,
            max_eta_minutes=max_eta_minutes,
            survival_time_minutes=survival_time_minutes,
            scenario_context=scenario_context,
            ml_score_override=ml_scores[i],
            pre_adjustments=scenario_adjustments,
            pre_model_features=model_features,
        )
        scored.append({**hospital, **final_res})

    scored.sort(key=lambda row: float(row.get("ml_score", row.get("score", 0.0))), reverse=True)
    return scored
