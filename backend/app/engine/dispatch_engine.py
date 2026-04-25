from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.db.models import Availability, Case, CaseEvent, Hospital
from app.engine.ml_scorer import rank_hospitals, _get_active_weights
from app.services.eta_service import get_eta

logger = logging.getLogger(__name__)

_SURVIVAL_BASELINES: dict[str, dict[str, float]] = {
    "cardiac": {"high": 14.0, "mid": 35.0, "low": 90.0},
    "stroke": {"high": 16.0, "mid": 45.0, "low": 120.0},
    "trauma": {"high": 22.0, "mid": 30.0, "low": 75.0},
    "respiratory": {"high": 12.0, "mid": 40.0, "low": 100.0},
    "burns": {"high": 25.0, "mid": 60.0, "low": 180.0},
    "obstetric": {"high": 20.0, "mid": 50.0, "low": 150.0},
    "general": {"high": 30.0, "mid": 75.0, "low": 240.0},
}

_STAGE1_EQUIPMENT_RULES: dict[str, tuple[str, float]] = {
    "cardiac": ("defibrillator", 8.0),
    "respiratory": ("ventilator", 10.0),
    "trauma": ("iv", 6.0),
    "stroke": ("oxygen", 5.0),
}

def _condition_required_equipment(condition: str, severity: int = 5) -> list[str]:
    """Returns required equipment for a condition, potentially severity-dependent."""
    base = {
        "cardiac": ["defibrillator"],
        "stroke": ["oxygen"],
        "trauma": ["iv"],
        "respiratory": ["oxygen"],
        "burns": ["iv"],
        "obstetric": ["iv", "oxygen"],
        "general": [],
    }
    reqs = base.get(condition, [])[:]
    if condition == "respiratory" and severity >= 8:
        reqs.append("ventilator")
    return reqs

CRITICAL_EQUIPMENT = {
    "ventilator", "defibrillator", "surgery", "blood_bank", 
    "cath_lab", "ct_scanner", "neurology", "trauma_center", "stroke_unit"
}
IMPORTANT_EQUIPMENT = {"icu", "trauma_care"}
OPTIONAL_EQUIPMENT = {"xray", "lab"}

_EQUIPMENT_ALIASES: dict[str, str] = {
    "icu_equipment": "icu",
    "ct_scan": "xray",
    "x_ray": "xray",
    "blood_bank": "lab",
    "laboratory": "lab",
}

_ICU_CONDITIONS = {"cardiac", "stroke", "trauma"}
_ETA_CACHE_TTL_SECONDS = 90
_ETA_CACHE: dict[tuple[float, float, float, float], tuple[float, float]] = {}
_LAST_VALID_ETA_BY_HOSPITAL: dict[int, float] = {}

# Calibrated stabilization times (minutes) for each condition
# These are applied when stabilize_first decision is made
_STABILIZATION_TIME_BY_CONDITION: dict[str, float] = {
    "cardiac": 10.0,      # IV access + basic monitoring
    "stroke": 15.0,       # Airway assessment + glucose check  
    "trauma": 20.0,       # Hemorrhage control + immobilization
    "respiratory": 12.0,  # Airway positioning + oxygen
    "burns": 18.0,        # Fluid resuscitation start
    "obstetric": 8.0,     # Initial assessment + fetal monitoring
    "general": 6.0,       # Basic triage
}


def normalize_condition_type(condition_type: str | None) -> str:
    condition = (condition_type or "").strip().lower()
    if condition in _SURVIVAL_BASELINES:
        return condition

    # Map existing condition labels to canonical Stage-1 condition groups.
    aliases = {
        "heart_attack": "cardiac",
        "cardiac_arrest": "cardiac",
        "head_injury": "trauma",
        "multi_trauma": "trauma",
        "severe_bleeding": "trauma",
        "respiratory_distress": "respiratory",
        "poisoning": "general",
        "minor_injury": "general",
        "fever": "general",
        "fracture": "general",
    }
    return aliases.get(condition, "general")


def normalize_severity_score(severity_score: int | str | None) -> int:
    if isinstance(severity_score, int):
        return max(1, min(10, severity_score))

    if severity_score is None:
        return 5

    value = str(severity_score).strip().lower()
    try:
        float_val = float(value)
        return max(1, min(10, int(round(float_val))))
    except ValueError:
        pass

    mapping = {
        "minor": 3,
        "low": 3,
        "moderate": 6,
        "medium": 6,
        "critical": 9,
        "high": 9,
    }
    return mapping.get(value, 5)


def _estimate_post_stabilization_severity(condition_type: str) -> int:
    canonical_condition = normalize_condition_type(condition_type)
    base_by_condition = {
        "cardiac": 9,
        "stroke": 9,
        "trauma": 8,
        "respiratory": 7,
        "burns": 6,
        "obstetric": 6,
        "general": 5,
    }
    return max(1, base_by_condition.get(canonical_condition, 5) - 2)


def _severity_band(severity_score: int) -> str:
    if severity_score >= 8:
        return "high"
    if severity_score >= 5:
        return "mid"
    return "low"


def _parse_systolic(bp_raw: Any) -> int | None:
    if bp_raw is None:
        return None
    try:
        bp_text = str(bp_raw).strip()
        if not bp_text:
            return None
        return int(bp_text.split("/")[0])
    except (TypeError, ValueError, IndexError):  # noqa: BLE001
        return None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _resolve_oxygen(vitals: dict[str, Any] | None) -> float:
    vitals = vitals or {}
    if "oxygen" in vitals:
        return _safe_float(vitals.get("oxygen"), 95.0)
    if "spo2" in vitals:
        return _safe_float(vitals.get("spo2"), 95.0)
    if "o2" in vitals:
        return _safe_float(vitals.get("o2"), 95.0)
    return 95.0


def _resolve_pulse(vitals: dict[str, Any] | None) -> float:
    vitals = vitals or {}
    if "pulse" in vitals:
        return _safe_float(vitals.get("pulse"), 80.0)
    if "heart_rate" in vitals:
        return _safe_float(vitals.get("heart_rate"), 80.0)
    return 80.0


def _resolve_systolic(vitals: dict[str, Any] | None) -> float:
    vitals = vitals or {}
    parsed = _parse_systolic(vitals.get("bp"))
    if parsed is not None:
        return float(parsed)
    if "systolic" in vitals:
        return _safe_float(vitals.get("systolic"), 120.0)
    if "systolic_bp" in vitals:
        return _safe_float(vitals.get("systolic_bp"), 120.0)
    return 120.0


def _is_unstable_case(*, condition_type: str, severity_score: int, vitals: dict[str, Any] | None) -> bool:
    oxygen = _resolve_oxygen(vitals)
    pulse = _resolve_pulse(vitals)
    systolic = _resolve_systolic(vitals)

    severe = int(severity_score) >= 8
    critical_vitals = oxygen < 90.0 or systolic < 90.0 or pulse > 130.0 or pulse < 45.0

    if condition_type in {"cardiac", "trauma"}:
        return severe or critical_vitals
    return critical_vitals


def _stable_vitals_hint(vitals: dict[str, Any] | None) -> bool:
    oxygen = _resolve_oxygen(vitals)
    pulse = _resolve_pulse(vitals)
    systolic = _resolve_systolic(vitals)
    return oxygen >= 94.0 and 60.0 <= pulse <= 100.0 and systolic >= 100.0


def _has_stroke_capability(hospital: dict[str, Any]) -> bool:
    tags = {str(item).strip().lower() for item in (hospital.get("scenario_tags") or []) if item}
    equipment = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
    return bool({"stroke", "neuro"} & tags) or bool({"ct_scan", "stroke_unit", "neurology"} & equipment)


def _has_trauma_stabilization_capability(hospital: dict[str, Any]) -> bool:
    tags = {str(item).strip().lower() for item in (hospital.get("scenario_tags") or []) if item}
    equipment = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
    hospital_type = _resolve_hospital_type(hospital)
    
    if "surgery" not in equipment:
        return False
        
    return (
        hospital_type in {"stabilization", "both"}
        or bool({"trauma"} & tags)
        or bool({"trauma_center", "lab"} & equipment)
    )


def _resolve_conflicts(
    *,
    condition_type: str,
    severity_score: int | str | None,
    vitals: dict[str, Any] | None,
    scenario_context: dict[str, Any] | None,
) -> tuple[str, int, dict[str, Any]]:
    explicit_condition = normalize_condition_type(condition_type)
    explicit_severity = normalize_severity_score(severity_score)
    vitals_payload = vitals or {}

    derived_condition_raw = (
        (scenario_context or {}).get("derived_condition")
        or (scenario_context or {}).get("nlp_condition")
        or (scenario_context or {}).get("text_condition")
        or (scenario_context or {}).get("ai_condition")
    )
    derived_condition = normalize_condition_type(str(derived_condition_raw or "")) if derived_condition_raw else None

    oxygen = _resolve_oxygen(vitals_payload)
    pulse = _resolve_pulse(vitals_payload)
    systolic = _resolve_systolic(vitals_payload)
    critical_vitals = oxygen < 90.0 or systolic < 90.0 or pulse > 130.0 or pulse < 45.0
    stable_vitals = _stable_vitals_hint(vitals_payload)

    resolved_condition = explicit_condition
    resolved_severity = explicit_severity
    trust_source = "explicit_conditions"
    conflict_detected = False
    conflict_flags: list[str] = []

    # Signal hierarchy: vitals > explicit_conditions > derived_text.
    if vitals_payload:
        trust_source = "vitals"
        if critical_vitals and explicit_severity < 8:
            resolved_severity = 8
            conflict_detected = True
            conflict_flags.append("vitals_override_severity_up")
        if stable_vitals and explicit_severity >= 8:
            resolved_severity = 7
            conflict_detected = True
            conflict_flags.append("vitals_override_severity_down")
    elif explicit_condition == "general" and derived_condition:
        trust_source = "derived_text"
        resolved_condition = derived_condition

    if derived_condition and explicit_condition != derived_condition:
        conflict_detected = True
        conflict_flags.append("explicit_vs_derived_conflict")

    return resolved_condition, resolved_severity, {
        "trust_source": trust_source,
        "conflict_detected": conflict_detected,
        "flags": conflict_flags,
        "explicit_condition": explicit_condition,
        "derived_condition": derived_condition,
        "resolved_condition": resolved_condition,
        "resolved_severity": resolved_severity,
    }


def _equipment_coverage(hospital: dict[str, Any], required: set[str]) -> float:
    if not required:
        return 1.0
    equipment = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
    return len(required & equipment) / max(1, len(required))


def _apply_behavior_corrections(
    *,
    ranked_candidates: list[dict[str, Any]],
    condition_type: str,
    required_equipment: list[str],
    unstable_case: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not ranked_candidates:
        return ranked_candidates, []

    corrected = [dict(item) for item in ranked_candidates]
    corrections: list[str] = []
    normalized_condition = normalize_condition_type(condition_type)

    if normalized_condition in {"cardiac", "trauma"} and unstable_case:
        for item in corrected:
            tags = {str(tag).strip().lower() for tag in (item.get("scenario_tags") or []) if tag}
            hospital_type = _resolve_hospital_type(item)
            stabilization_ready = (
                hospital_type in {"stabilization", "both"}
                or "trauma" in tags
            )
            item["behavior_stabilization_ready"] = 1.0 if stabilization_ready else 0.0
            if not stabilization_ready:
                item["score"] = round(float(item.get("score", 0.0)) * 0.20, 6)
        if normalized_condition == "cardiac":
            corrections.append("cardiac_unstable_stabilization_priority_enforced")
        else:
            corrections.append("trauma_unstable_stabilization_priority_enforced")

    if normalized_condition == "stroke":
        capable = [item for item in corrected if _has_stroke_capability(item)]
        if capable:
            for item in corrected:
                if not _has_stroke_capability(item):
                    item["score"] = round(float(item.get("score", 0.0)) * 0.20, 6)
            corrections.append("stroke_neuro_penalty_applied")

    if normalized_condition == "respiratory":
        respiratory_required = {
            _normalize_equipment_name(item)
            for item in required_equipment
            if _normalize_equipment_name(item) in {"oxygen", "ventilator"}
        }
        if respiratory_required:
            for item in corrected:
                coverage = _equipment_coverage(item, respiratory_required)
                item["behavior_equipment_coverage"] = round(float(coverage), 6)
                if coverage < 1.0:
                    item["score"] = round(float(item.get("score", 0.0)) * 0.40, 6)
            corrections.append("respiratory_equipment_priority_enforced")

    corrected.sort(
        key=lambda item: (
            float(item.get("behavior_stabilization_ready", 1.0)),
            float(item.get("behavior_equipment_coverage", 1.0)),
            float(item.get("score", 0.0)),
            -float(item.get("eta_minutes", 9999.0)),
        ),
        reverse=True,
    )
    return corrected, corrections


def _detect_input_corruption(
    *,
    severity_score: int,
    vitals: dict[str, Any] | None,
    hospitals: list[dict[str, Any]],
    gps_anomaly_count: int,
) -> dict[str, Any]:
    signals: list[str] = []
    vitals = vitals or {}

    if not vitals or not any(key in vitals for key in ["oxygen", "pulse", "bp"]):
        signals.append("missing_vitals")

    oxygen_value = _safe_float(vitals.get("oxygen"), 95.0)
    if severity_score >= 8 and _stable_vitals_hint(vitals):
        signals.append("severity_vitals_conflict")
    if severity_score <= 3 and oxygen_value < 85.0:
        signals.append("severity_vitals_conflict")

    for hospital in hospitals:
        for item in hospital.get("equipment", []) or []:
            normalized_item = str(item or "").strip().lower()
            if normalized_item and re.search(r"[^a-z0-9_\-\s]", normalized_item):
                signals.append("corrupted_equipment_labels")
                break
        load_value = hospital.get("hospital_load")
        if load_value is not None:
            load = _safe_float(load_value, 0.0)
            if load < 0.0 or load > 1.0:
                signals.append("invalid_load_range")

    if gps_anomaly_count > 0:
        signals.append("gps_anomaly")

    # Deduplicate while preserving deterministic order.
    deduped_signals = list(dict.fromkeys(signals))
    return {
        "input_corruption_detected": bool(deduped_signals),
        "corruption_signals": deduped_signals,
    }


def evaluate_stability(
    *,
    condition_type: str,
    severity_score: int,
    vitals: dict[str, Any] | None,
    ambulance_equipment: list[str] | None,
    eta_to_nearest_hospital: float,
) -> dict[str, Any]:
    canonical_condition = normalize_condition_type(condition_type)
    normalized_severity = normalize_severity_score(severity_score)
    baseline = _SURVIVAL_BASELINES[canonical_condition][_severity_band(normalized_severity)]

    equipment_set = {str(item).strip().lower() for item in (ambulance_equipment or []) if item}
    missing_equipment: list[str] = []
    estimated_survival = baseline

    # Base oxygen requirement across all conditions.
    if "oxygen" not in equipment_set:
        estimated_survival -= 3.0
        missing_equipment.append("oxygen")

    if canonical_condition in _STAGE1_EQUIPMENT_RULES:
        required_item, penalty = _STAGE1_EQUIPMENT_RULES[canonical_condition]
        if required_item not in equipment_set:
            estimated_survival -= penalty
            if required_item not in missing_equipment:
                missing_equipment.append(required_item)

    vitals_flags: list[str] = []

    oxygen = _resolve_oxygen(vitals)
    if oxygen < 90:
        estimated_survival -= 10.0
        vitals_flags.append("oxygen_below_90")

    pulse = _resolve_pulse(vitals)
    if pulse > 140 or pulse < 40:
        estimated_survival -= 8.0
        vitals_flags.append("pulse_critical")

    systolic = _resolve_systolic(vitals)
    if systolic < 80:
        estimated_survival -= 12.0
        vitals_flags.append("bp_systolic_below_80")

    estimated_survival = max(1.0, round(estimated_survival, 2))
    eta = max(0.1, float(eta_to_nearest_hospital))
    stability_score = round(estimated_survival / (estimated_survival + eta), 4)
    # Extreme Risk (9.2+) forces stabilization only if hub is > 10 min away.
    # High Risk (8.0+) uses 1.8x, otherwise 1.3x.
    if normalized_severity >= 9.2:
        risk_multiplier = 2.2 if eta > 10.0 else 1.5
    elif normalized_severity >= 8.0:
        risk_multiplier = 1.8
    else:
        risk_multiplier = 1.3
        
    stabilization_required = estimated_survival < (eta * risk_multiplier)

    return {
        "stability_score": stability_score,
        "estimated_survival_time": estimated_survival,
        "stabilization_required": stabilization_required,
        "missing_equipment": sorted(missing_equipment),
        "vitals_flags": vitals_flags,
        "risk_multiplier_applied": risk_multiplier,
    }


def _eta_cache_key(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> tuple[float, float, float, float]:
    return (round(origin_lat, 5), round(origin_lng, 5), round(dest_lat, 5), round(dest_lng, 5))


async def _fetch_eta_map(
    *,
    origin_lat: float,
    origin_lng: float,
    hospitals: list[dict[str, Any]],
    include_metadata: bool = False,
) -> dict[int, float] | tuple[dict[int, float], dict[str, int]]:
    now = time.time()
    eta_map: dict[int, float] = {}
    metadata: dict[str, int] = {
        "gps_anomaly_detected": 0,
        "gps_swap_corrected": 0,
        "last_known_eta_used": 0,
        "distance_estimate_used": 0,
    }

    # Prevent unbounded growth when many origin/destination pairs are seen.
    if len(_ETA_CACHE) > 5000:
        _ETA_CACHE.clear()

    uncached: list[dict[str, Any]] = []
    for hospital in hospitals:
        raw_id = hospital.get("id") or hospital.get("hospital_id")
        try:
            hospital_id = int(raw_id) if str(raw_id).isdigit() else raw_id
        except (ValueError, TypeError):
            hospital_id = raw_id

        # If hospital lacks coordinates, preserve its baked-in ETA (for test harness)
        if hospital.get("latitude") is None or hospital.get("longitude") is None:
            if "eta_minutes" in hospital:
                eta_map[hospital_id] = float(hospital["eta_minutes"])
            continue

        raw_lat = _safe_float(hospital.get("latitude"), origin_lat)
        raw_lng = _safe_float(hospital.get("longitude"), origin_lng)

        lat = raw_lat
        lng = raw_lng
        gps_anomaly = abs(lat - origin_lat) > 1.5 or abs(lng - origin_lng) > 1.5
        if gps_anomaly:
            metadata["gps_anomaly_detected"] += 1
            swapped_lat = raw_lng
            swapped_lng = raw_lat
            swap_is_valid = -90.0 <= swapped_lat <= 90.0 and -180.0 <= swapped_lng <= 180.0

            raw_gap = abs(raw_lat - origin_lat) + abs(raw_lng - origin_lng)
            swapped_gap = abs(swapped_lat - origin_lat) + abs(swapped_lng - origin_lng)
            if swap_is_valid and swapped_gap < raw_gap:
                lat = swapped_lat
                lng = swapped_lng
                metadata["gps_swap_corrected"] += 1

        hospital["latitude"] = float(lat)
        hospital["longitude"] = float(lng)

        if gps_anomaly and hospital_id in _LAST_VALID_ETA_BY_HOSPITAL:
            eta_map[hospital_id] = _LAST_VALID_ETA_BY_HOSPITAL[hospital_id]
            metadata["last_known_eta_used"] += 1
            continue

        key = _eta_cache_key(origin_lat, origin_lng, lat, lng)
        cached = _ETA_CACHE.get(key)
        if cached and (now - cached[0]) <= _ETA_CACHE_TTL_SECONDS:
            eta_map[hospital_id] = cached[1]
        else:
            uncached.append(hospital)

    if not uncached:
        if include_metadata:
            return eta_map, metadata
        return eta_map

    async def _resolve_single_eta(hospital: dict[str, Any]) -> tuple[int, float, tuple[float, float, float, float], bool]:
        key = _eta_cache_key(origin_lat, origin_lng, hospital["latitude"], hospital["longitude"])
        loop = asyncio.get_running_loop()
        eta_minutes = await loop.run_in_executor(
            None,
            lambda: get_eta(
                origin_lat,
                origin_lng,
                float(hospital["latitude"]),
                float(hospital["longitude"]),
            ),
        )
        used_distance_estimate = float(eta_minutes) >= 9999.0
        
        raw_id = hospital.get("id") or hospital.get("hospital_id")
        try:
            h_id = int(raw_id) if str(raw_id).isdigit() else raw_id
        except (ValueError, TypeError):
            h_id = raw_id
            
        return h_id, max(0.1, float(eta_minutes)), key, used_distance_estimate

    resolved = await asyncio.gather(*[_resolve_single_eta(hospital) for hospital in uncached])
    for hospital_id, eta_minutes, key, used_distance_estimate in resolved:
        eta_map[hospital_id] = eta_minutes
        _ETA_CACHE[key] = (now, eta_minutes)
        if 0.1 <= eta_minutes <= 180.0:
            _LAST_VALID_ETA_BY_HOSPITAL[hospital_id] = eta_minutes
        if used_distance_estimate:
            metadata["distance_estimate_used"] += 1

    if include_metadata:
        return eta_map, metadata
    return eta_map


def _resolve_hospital_type(hospital: dict[str, Any]) -> str:
    raw = hospital.get("hospital_type")
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"stabilization", "advanced", "both"}:
            return value
        if value == "tertiary":
            return "advanced"
        if value == "specialized":
            return "both"
        if value == "secondary":
            return "stabilization"
        if value == "primary":
            return "stabilization"

    specialists = hospital.get("specialists")
    if isinstance(specialists, dict):
        nested = specialists.get("hospital_type")
        if isinstance(nested, str):
            value = nested.strip().lower()
            if value in {"stabilization", "advanced", "both"}:
                return value

    # Fallback for unknown internal types
    return "basic"


def _requires_icu(condition_type: str, severity_score: int) -> bool:
    return condition_type in _ICU_CONDITIONS and severity_score >= 7


def _condition_required_equipment_proxy(condition_type: str) -> list[str]:
    # Legacy wrapper for cases where only condition is known
    return _condition_required_equipment(condition_type, 5)


def _normalize_equipment_name(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = normalized.replace("-", "_")
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)
    noisy_aliases = {
        "oxyg3n": "oxygen",
        "defib": "defibrillator",
        "defibrilator": "defibrillator",
        "ventlator": "ventilator",
        "ctscn": "ct_scan",
        "traum": "trauma_center",
    }
    normalized = noisy_aliases.get(normalized, normalized)
    return _EQUIPMENT_ALIASES.get(normalized, normalized)


def _equipment_ratio(required: set[str], available: set[str]) -> float:
    if not required:
        return 1.0
    matched = len(required & available)
    return matched / len(required)


def _apply_tiebreaker(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Apply tie-breaker logic to produce a deterministic ranking when hospitals
    have near-identical composite scores.

    Problem with the previous approach: a single forward pass comparing adjacent
    pairs is one step of bubble sort — it only fixes one inversion per call and
    leaves the final order dependent on input list ordering.

    This replacement uses a proper stable sort on a composite key:
      1. score_bucket  — score rounded to nearest 0.05, so hospitals within the
                         tie threshold land in the same bucket and compete on
                         subsequent keys rather than raw float noise.
      2. S_treatment   — condition-specific treatment capability (descending).
      3. S_equipment   — equipment match quality (descending).
      4. hospital_id   — string sort (ascending) as final deterministic tiebreaker.
                         Stable across repeated calls regardless of input list order.

    Notes on ID safety: all hospital_id values in this system are strings
    (e.g. "cardiac_hub_main", "general_sec_1"). str(raw_id) safely handles
    integer IDs and None (sorts as "None") if those ever appear.
    """
    if len(candidates) < 2:
        return candidates

    _TIE_BUCKET = 0.05

    def _tiebreak_key(item: dict[str, Any]) -> tuple:
        score = float(item.get("score", 0.0))
        breakdown = item.get("score_breakdown") or {}
        treatment = float(breakdown.get("S_treatment", 0.0))
        equipment = float(breakdown.get("S_equipment", 0.0))
        # Round into buckets so hospitals within the tie threshold compete on
        # the sub-keys rather than raw score noise.
        score_bucket = round(score / _TIE_BUCKET) * _TIE_BUCKET
        raw_id = item.get("id") or item.get("hospital_id") or ""
        # All components negated where higher-is-better so sorted() ascending = best-first.
        return (-score_bucket, -treatment, -equipment, str(raw_id))

    return sorted(candidates, key=_tiebreak_key)


def _penalize_lazy_safe_choice(
    *,
    ranked_candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    if len(ranked_candidates) < 2:
        return ranked_candidates, False

    candidates = [dict(item) for item in ranked_candidates]
    top = candidates[0]
    partial_match = bool(top.get("missing_important_equipment"))
    if not partial_match:
        return candidates, False

    top_score = float(top.get("score", 0.0) or 0.0)
    top_breakdown = top.get("score_breakdown", {}) or {}
    top_treatment = float(top_breakdown.get("S_treatment", 0.0) or 0.0)
    top_equipment = float(top_breakdown.get("S_equipment", 0.0) or 0.0)

    better_specialized_exists = any(
        (float((candidate.get("score_breakdown", {}) or {}).get("S_treatment", 0.0) or 0.0) > (top_treatment + 0.15))
        and (float((candidate.get("score_breakdown", {}) or {}).get("S_equipment", 0.0) or 0.0) >= top_equipment)
        and (float(candidate.get("score", 0.0) or 0.0) >= (top_score * 0.85))
        for candidate in candidates[1:]
    )

    if not better_specialized_exists:
        return candidates, False

    top["score"] = round(top_score * 0.6, 6)
    top.setdefault("score_breakdown", {})
    top["score_breakdown"]["lazy_safe_penalty"] = 0.6
    candidates[0] = top
    candidates.sort(key=lambda item: (float(item.get("score", 0.0)) * -1, float(item.get("eta_minutes", 9999.0))))
    return candidates, True


def _get_stabilization_time(condition_type: str) -> float:
    """Get calibrated stabilization time for condition (minutes)"""
    canonical = normalize_condition_type(condition_type)
    return _STABILIZATION_TIME_BY_CONDITION.get(canonical, 6.0)


def _categorize_required_equipment(required_equipment: list[str]) -> dict[str, set[str]]:
    categories = {
        "critical": set(),
        "important": set(),
        "optional": set(),
    }
    for raw in required_equipment:
        normalized = _normalize_equipment_name(raw)
        if not normalized:
            continue
        if normalized in CRITICAL_EQUIPMENT:
            categories["critical"].add(normalized)
        elif normalized in OPTIONAL_EQUIPMENT:
            categories["optional"].add(normalized)
        else:
            # Unknown/legacy equipment defaults to important so it influences scoring
            # without becoming a hard reject.
            categories["important"].add(normalized)
    return categories


def _compute_equipment_match_score(
    required_by_tier: dict[str, set[str]],
    hospital_equipment_set: set[str],
    *,
    relax_important: bool,
    important_penalty: float,
) -> float:
    critical_ratio = _equipment_ratio(required_by_tier["critical"], hospital_equipment_set)
    important_ratio = 1.0 if relax_important else _equipment_ratio(required_by_tier["important"], hospital_equipment_set)
    optional_ratio = _equipment_ratio(required_by_tier["optional"], hospital_equipment_set)
    raw_score = (critical_ratio * 0.6) + (important_ratio * 0.3) + (optional_ratio * 0.1)
    return round(max(0.0, raw_score - important_penalty), 6)


def _hospital_satisfies_constraints(
    *,
    hospital: dict[str, Any],
    required_equipment_by_tier: dict[str, set[str]],
    condition_type: str,
    high_risk_case: bool,
    icu_required: bool,
    allowed_hospital_types: set[str] | None,
) -> bool:
    equipment_set = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}

    critical_required = required_equipment_by_tier["critical"]
    if critical_required and not critical_required.issubset(equipment_set):
        return False

    has_icu = bool(hospital.get("has_ICU"))
    if not has_icu:
        has_icu = int(hospital.get("icu_beds") or 0) > 0 or "icu" in equipment_set
    if icu_required and not has_icu:
        return False

    hospital_type = _resolve_hospital_type(hospital)
    if allowed_hospital_types and hospital_type not in allowed_hospital_types:
        return False

    # Hard reject high-risk capability gaps.
    if high_risk_case and condition_type == "stroke" and not _has_stroke_capability(hospital):
        return False
    if condition_type == "trauma" and not _has_trauma_stabilization_capability(hospital):
        return False

    return True


def _enforce_post_ranking_constraints(
    *,
    ranked_candidates: list[dict[str, Any]],
    required_equipment: list[str],
    condition_type: str,
    severity_score: int,
    allowed_hospital_types: set[str] | None,
    relax_important_constraints: bool,
) -> list[dict[str, Any]]:
    """Safety layer: ensures downstream ranking/ML never bypasses hard constraints."""
    required_by_tier = _categorize_required_equipment(required_equipment)
    icu_required = _requires_icu(condition_type, severity_score)
    high_risk_case = int(severity_score) >= 8
    normalized_condition = normalize_condition_type(condition_type)
    effective_allowed_types = None if relax_important_constraints else allowed_hospital_types

    filtered: list[dict[str, Any]] = []
    dropped = 0
    for candidate in ranked_candidates:
        if _hospital_satisfies_constraints(
            hospital=candidate,
            required_equipment_by_tier=required_by_tier,
            condition_type=normalized_condition,
            high_risk_case=high_risk_case,
            icu_required=icu_required,
            allowed_hospital_types=effective_allowed_types,
        ):
            filtered.append(candidate)
        else:
            dropped += 1

    if dropped:
        logger.warning(
            "Post-ranking constraint enforcement dropped %s candidate(s); ML/ranker cannot override hard constraints.",
            dropped,
        )

    return filtered


def _format_destination(hospital: dict[str, Any], ml_score: float | None) -> dict[str, Any]:
    raw_id = hospital.get("id") or hospital.get("hospital_id")
    try:
        if raw_id is not None and str(raw_id).isdigit():
            h_id = int(raw_id)
        else:
            h_id = raw_id
    except (ValueError, TypeError):
        h_id = raw_id
        
    return {
        "hospital_id": h_id,
        "hospital_name": hospital.get("name", "Unknown"),
        "eta_minutes": round(float(hospital.get("eta_minutes", 0.0)), 2),
        "hospital_type": hospital.get("hospital_type", "both"),
        "ml_score": round(float(ml_score), 4) if ml_score is not None else None,
        "score_breakdown": hospital.get("score_breakdown", {}),
        "address": hospital.get("address") or "",
    }


def _apply_hard_constraints(
    *,
    hospitals: list[dict[str, Any]],
    required_equipment: list[str],
    condition_type: str,
    severity_score: int,
    allowed_hospital_types: set[str] | None,
    relax_important_constraints: bool,
    relaxed_constraints_mode: bool,
) -> tuple[list[dict[str, Any]], dict[str, int], list[str]]:
    constraint_counts = {
        "accepting_false": 0,
        "no_available_beds": 0,
        "hospital_overloaded": 0,
        "missing_critical_equipment": 0,
        "important_equipment_penalty_applied": 0,
        "missing_icu": 0,
        "hospital_type_mismatch": 0,
        "missing_neuro_capability": 0,
        "missing_stabilization_capability": 0,
    }

    normalized_condition = normalize_condition_type(condition_type)
    high_risk_case = int(severity_score) >= 8
    icu_required = _requires_icu(condition_type, severity_score)
    required_by_tier = _categorize_required_equipment(required_equipment)
    passed: list[dict[str, Any]] = []

    for hospital in hospitals:
        rejected = False
        equipment_set = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
        hospital["hospital_type"] = _resolve_hospital_type(hospital)

        if not bool(hospital.get("accepting", True)):
            constraint_counts["accepting_false"] += 1
            if not relaxed_constraints_mode:
                rejected = True

        if int(hospital.get("available_beds") or 1) <= 0:
            constraint_counts["no_available_beds"] += 1
            if not relaxed_constraints_mode:
                rejected = True

        hospital_load = _safe_float(hospital.get("hospital_load"), 0.0)
        if hospital_load >= 0.9:
            constraint_counts["hospital_overloaded"] += 1
            if not relaxed_constraints_mode:
                rejected = True

        missing_critical = [eq for eq in required_by_tier["critical"] if eq not in equipment_set]
        if missing_critical:
            constraint_counts["missing_critical_equipment"] += 1
            rejected = True

        missing_important: list[str] = []
        if not relax_important_constraints:
            missing_important = [eq for eq in required_by_tier["important"] if eq not in equipment_set]
            if missing_important:
                constraint_counts["important_equipment_penalty_applied"] += 1

        has_icu = bool(hospital.get("has_ICU"))
        if not has_icu:
            has_icu = int(hospital.get("icu_beds") or 0) > 0 or "icu" in equipment_set
        hospital["has_ICU"] = has_icu

        if icu_required and not has_icu:
            constraint_counts["missing_icu"] += 1
            rejected = True

        if allowed_hospital_types and hospital["hospital_type"] not in allowed_hospital_types:
            constraint_counts["hospital_type_mismatch"] += 1
            if not relaxed_constraints_mode:
                rejected = True

        if high_risk_case and normalized_condition == "stroke" and not _has_stroke_capability(hospital):
            constraint_counts["missing_neuro_capability"] += 1
            rejected = True

        if high_risk_case and normalized_condition == "trauma" and not _has_trauma_stabilization_capability(hospital):
            constraint_counts["missing_stabilization_capability"] += 1
            rejected = True

        important_penalty = min(0.30, 0.10 * len(missing_important))

        hospital["equipment_match_score"] = _compute_equipment_match_score(
            required_by_tier,
            equipment_set,
            relax_important=relax_important_constraints,
            important_penalty=important_penalty,
        )
        hospital["matched_critical_equipment"] = sorted(required_by_tier["critical"] & equipment_set)
        hospital["missing_critical_equipment"] = sorted(missing_critical)
        hospital["missing_important_equipment"] = sorted(missing_important)
        hospital["missing_optional_equipment"] = sorted(
            eq for eq in required_by_tier["optional"] if eq not in equipment_set
        )
        hospital["important_equipment_penalty"] = important_penalty

        if not rejected:
            passed.append(hospital)

    constraints_applied = [
        "exclude_if_accepting_false",
        "exclude_if_available_beds_zero",
        "exclude_if_hospital_overloaded",
        "exclude_if_missing_critical_equipment",
        "penalize_if_missing_important_equipment",
    ]
    if icu_required:
        constraints_applied.append("exclude_if_missing_icu")
    if allowed_hospital_types:
        constraints_applied.append("filter_hospital_type_in_" + "_or_".join(sorted(allowed_hospital_types)))
    if relaxed_constraints_mode:
        constraints_applied.append("relaxed_constraints_mode")

    return passed, constraint_counts, constraints_applied


def _classify_fallback_triggers(
    *,
    constraint_counts: dict[str, int],
    no_viable_after_constraints: bool,
    eta_minutes: float,
    estimated_survival_time: float,
    input_corruption_detected: bool,
) -> list[str]:
    triggers: list[str] = []
    if constraint_counts.get("missing_critical_equipment", 0) > 0:
        triggers.append("missing_critical_equipment")
    if no_viable_after_constraints:
        triggers.append("no_viable_hospital_after_constraints")
    if eta_minutes > max(20.0, estimated_survival_time * 1.5):
        triggers.append("eta_too_high")
    if estimated_survival_time < 8.0:
        triggers.append("survival_below_threshold")
    if input_corruption_detected:
        triggers.append("corrupted_input_detected")
    return triggers


def _build_stabilization_pool(
    *,
    hospitals: list[dict[str, Any]],
    condition_type: str,
    severity_score: int,
) -> list[dict[str, Any]]:
    """
    Build a candidate pool for stabilize_first decisions.
    Filters only on stabilization capability and operational constraints.
    Does NOT apply destination-specific equipment requirements (neurology,
    cath_lab, etc.) — those belong to the final transfer destination, not
    the stabilization center.
    """
    normalized_condition = normalize_condition_type(condition_type)
    icu_required = _requires_icu(condition_type, severity_score)
    pool: list[dict[str, Any]] = []

    for hospital in hospitals:
        hospital_type = _resolve_hospital_type(hospital)

        # Must be a stabilization-capable type.
        if hospital_type not in {"stabilization", "both"}:
            continue

        # Must be accepting and have available beds.
        if not bool(hospital.get("accepting", True)):
            continue
        if int(hospital.get("available_beds") or 0) <= 0:
            continue

        # ICU required for high-severity cardiac/stroke/trauma.
        if icu_required:
            has_icu = bool(hospital.get("has_ICU")) or int(hospital.get("icu_beds") or 0) > 0
            equipment_set = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
            if not has_icu and "icu" not in equipment_set:
                continue

        enriched = dict(hospital)
        enriched["hospital_type"] = hospital_type
        enriched["has_ICU"] = bool(hospital.get("has_ICU")) or int(hospital.get("icu_beds") or 0) > 0
        enriched["missing_critical_equipment"] = []
        enriched["missing_important_equipment"] = []
        enriched["important_equipment_penalty"] = 0.0
        enriched["equipment_match_score"] = 1.0
        pool.append(enriched)

    return pool


def _build_critical_safe_pool(
    *,
    hospitals: list[dict[str, Any]],
    required_equipment: list[str],
    condition_type: str,
    severity_score: int,
    trimodal_crisis: bool = False,
    survival_critical: bool = False,
) -> list[dict[str, Any]]:
    required_by_tier = _categorize_required_equipment(required_equipment)
    normalized_condition = normalize_condition_type(condition_type)
    high_risk_case = int(severity_score) >= 8
    icu_required = _requires_icu(condition_type, severity_score)

    pool: list[dict[str, Any]] = []
    for hospital in hospitals:
        equipment_set = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
        missing_critical = sorted(eq for eq in required_by_tier["critical"] if eq not in equipment_set)

        has_icu = bool(hospital.get("has_ICU"))
        if not has_icu:
            has_icu = int(hospital.get("icu_beds") or 0) > 0 or "icu" in equipment_set

        if missing_critical:
            continue
        if icu_required and not has_icu:
            continue
        if high_risk_case and normalized_condition == "stroke" and not _has_stroke_capability(hospital):
            continue
        if high_risk_case and normalized_condition == "trauma" and not _has_trauma_stabilization_capability(hospital):
            continue

        missing_important = sorted(eq for eq in required_by_tier["important"] if eq not in equipment_set)
        important_penalty = min(0.30, 0.10 * len(missing_important))

        enriched = dict(hospital)
        enriched["hospital_type"] = _resolve_hospital_type(hospital)
        enriched["has_ICU"] = has_icu
        enriched["missing_critical_equipment"] = missing_critical
        enriched["missing_important_equipment"] = missing_important
        enriched["important_equipment_penalty"] = important_penalty
        enriched["equipment_match_score"] = _compute_equipment_match_score(
            required_by_tier,
            equipment_set,
            relax_important=True,
            important_penalty=important_penalty,
        )
        pool.append(enriched)

    # Fix B: Last-resort routing for trimodal crisis patients.
    # If all constraints filtered every hospital and this is a trimodal crisis,
    # select the best available hospital ignoring equipment constraints.
    # Tagged partial_match_last_resort=True so dispatchers know the compromise.
    if not pool and (trimodal_crisis or survival_critical):
        candidates = [h for h in hospitals if int(h.get("available_beds") or 0) > 0]
        if candidates:
            best = max(
                candidates,
                key=lambda h: (
                    bool(h.get("has_ICU")) or int(h.get("icu_beds") or 0) > 0,
                    int(h.get("available_beds") or 0),
                ),
            )
            enriched = dict(best)
            enriched["hospital_type"] = _resolve_hospital_type(best)
            enriched["has_ICU"] = bool(best.get("has_ICU")) or int(best.get("icu_beds") or 0) > 0
            enriched["missing_critical_equipment"] = []
            enriched["missing_important_equipment"] = []
            enriched["important_equipment_penalty"] = 0.0
            enriched["equipment_match_score"] = 0.0
            enriched["partial_match_last_resort"] = True
            pool.append(enriched)

    return pool


def _best_effort_rank(
    *,
    hospitals: list[dict[str, Any]],
    ambulance_lat: float,
    ambulance_lng: float,
    required_equipment: list[str],
    condition_type: str,
    ambulance_equipment: list[str] | None,
    severity_score: int,
    survival_time_minutes: float,
    scenario_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    try:
        ranked = rank_hospitals(
            hospitals,
            ambulance_lat=ambulance_lat,
            ambulance_lon=ambulance_lng,
            required_equipment=required_equipment,
            condition=condition_type,
            ambulance_equipment=ambulance_equipment,
            severity_score=severity_score,
            survival_time_minutes=survival_time_minutes,
            scenario_context=scenario_context,
        )
        return sorted(
            ranked,
            key=lambda item: (float(item.get("score", 0.0)) * -1, float(item.get("eta_minutes", 9999.0))),
        )
    except (KeyError, TypeError, ValueError, RuntimeError):
        ranked = sorted(hospitals, key=lambda item: float(item.get("eta_minutes", 9999.0)))
        for candidate in ranked:
            candidate["score"] = round(1.0 / (1.0 + float(candidate.get("eta_minutes", 9999.0))), 6)
            candidate["score_breakdown"] = {
                "distance_score": 0.0,
                "bed_score": 0.0,
                "specialist_present": bool(candidate.get("specialist_count", 0) > 0),
                "equipment_match": float(candidate.get("equipment_match_score", 0.0)),
                "distance_km": round(float(candidate.get("eta_minutes", 9999.0)) * (40.0 / 60.0), 2),
            }
            candidate["pros"] = ["Best-effort ETA ranking used"]
            candidate["cons"] = []
            candidate["explanation"] = ["Best-effort fallback ranking due scorer exception."]
        return ranked

_TRIMODAL_CRISIS_FLAGS = frozenset({"oxygen_below_90", "pulse_critical", "bp_systolic_below_80"})

async def run_dispatch(
    *,
    case_id: str | None = None,
    hospitals: list[dict[str, Any]],
    ambulance_lat: float,
    ambulance_lng: float,
    condition_type: str,
    severity_score: int | str | None,
    vitals: dict[str, Any] | None,
    ambulance_equipment: list[str] | None,
    required_equipment: list[str],
    forced_hospital_types: set[str] | None = None,
    force_direct: bool = False,
    relax_important_constraints: bool = False,
    enable_adaptive_constraints: bool = True,
    scenario_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    logger.info(
        "Routing decision started condition=%s severity=%s hospitals=%s force_direct=%s forced_types=%s",
        condition_type,
        severity_score,
        len(hospitals),
        force_direct,
        sorted(forced_hospital_types) if forced_hospital_types else None,
    )

    scenario_ctx = dict(scenario_context or {})
    canonical_condition, normalized_severity, signal_resolution = _resolve_conflicts(
        condition_type=condition_type,
        severity_score=severity_score,
        vitals=vitals,
        scenario_context=scenario_ctx,
    )
    scenario_ctx["signal_resolution"] = signal_resolution
    if signal_resolution.get("conflict_detected"):
        scenario_ctx["conflicting_signals"] = True

    replay_required_equipment = sorted(
        {str(item).strip().lower() for item in (required_equipment or []) if item}
    )
    replay_nearest_eta = 0.0
    replay_estimated_survival = 0.0
    replay_stability_score = 0.0
    replay_constraints_counts: dict[str, int] = {}
    replay_relaxed_constraints_mode = bool(relax_important_constraints)
    replay_corruption_signals: list[str] = []
    if os.getenv("TRUST_TRACE_SIGNALS", "0") == "1":
        logger.debug("Dispatch received scenario_ctx=%s", scenario_ctx)
    allowed_types = forced_hospital_types

    def _safe_active_weights() -> dict[str, float]:
        try:
            return {
                key: round(float(value), 6)
                for key, value in _get_active_weights().items()
            }
        except (RuntimeError, ValueError, TypeError, KeyError):
            return {
                "w_survival": 0.30,
                "w_treatment": 0.25,
                "w_equipment": 0.20,
                "w_eta": 0.15,
                "w_load": 0.10,
            }

    def _is_borderline_decision(ranked_candidates: list[dict[str, Any]]) -> bool:
        if len(ranked_candidates) < 2:
            return False
        first = float(ranked_candidates[0].get("score", 0.0) or 0.0)
        second = float(ranked_candidates[1].get("score", 0.0) or 0.0)
        return abs(first - second) < 0.05

    def _build_replay_snapshot(decision: dict[str, Any]) -> dict[str, Any]:
        ranked_candidates = decision.get("ranked_candidates") or []
        candidate_pool = ranked_candidates if ranked_candidates else hospitals
        reasoning = decision.get("reasoning", {}) or {}
        top_breakdown = (ranked_candidates[0].get("score_breakdown", {}) if ranked_candidates else {}) or {}

        final_score = (
            float(ranked_candidates[0].get("score", 0.0) or 0.0)
            if ranked_candidates
            else float(reasoning.get("ml_score", 0.0) or 0.0)
        )

        fallback_used = bool(reasoning.get("fallback_triggers")) or (
            str(decision.get("decision_type", "")).strip().lower() == "no_viable_hospital"
        )

        return {
            "case_input": {
                "case_id": case_id or "unknown",
                "condition_type": str(condition_type or "general"),
                "condition_type_canonical": canonical_condition,
                "severity_score": float(normalized_severity),
                "vitals": vitals or {},
                "required_equipment": replay_required_equipment,
                "scenario_name": scenario_ctx.get("scenario_name"),
                "scenario_priority_type": scenario_ctx.get("priority_type"),
                "expected_behavior": scenario_ctx.get("expected_behavior"),
                "forced_hospital_types": sorted(allowed_types) if allowed_types else [],
                "force_direct": bool(force_direct),
                "relax_important_constraints": bool(relax_important_constraints),
                "enable_adaptive_constraints": bool(enable_adaptive_constraints),
            },
            "ambulance_data": {
                "ambulance_lat": float(ambulance_lat),
                "ambulance_lng": float(ambulance_lng),
                "ambulance_equipment": [str(item).strip().lower() for item in (ambulance_equipment or []) if item],
            },
            "hospital_candidates": candidate_pool,
            "final_decision": decision,
            "component_scores": {
                "S_survival": float(top_breakdown.get("S_survival", 0.0) or 0.0),
                "S_treatment": float(top_breakdown.get("S_treatment", 0.0) or 0.0),
                "S_equipment": float(top_breakdown.get("S_equipment", 0.0) or 0.0),
                "S_eta": float(top_breakdown.get("S_eta", 0.0) or 0.0),
                "S_load": float(top_breakdown.get("S_load", 0.0) or 0.0),
                "final_score": round(final_score, 6),
            },
            "weights": _safe_active_weights(),
            "flags": {
                "fallback_used": fallback_used,
                "relaxed_constraints": replay_relaxed_constraints_mode,
                "borderline": _is_borderline_decision(ranked_candidates),
                "partial_match_selected": bool(reasoning.get("partial_match_selected", False)),
                "behavior_corrections": reasoning.get("behavior_corrections") or [],
            },
            "replay_params": {
                "decision_type": str(decision.get("decision_type", "unknown")),
                "ambulance_lat": float(ambulance_lat),
                "ambulance_lng": float(ambulance_lng),
                "required_equipment": replay_required_equipment,
                "condition_type": str(condition_type or "general"),
                "condition_type_canonical": canonical_condition,
                "severity_score": int(normalized_severity),
                "survival_time_minutes": float(replay_estimated_survival),
                "nearest_eta_minutes": float(replay_nearest_eta),
                "stability_score": float(replay_stability_score),
                "constraints_counts": replay_constraints_counts,
                "corruption_signals": replay_corruption_signals,
                "scenario_context": {
                    "scenario_name": scenario_ctx.get("scenario_name"),
                    "priority_type": scenario_ctx.get("priority_type"),
                    "expected_behavior": scenario_ctx.get("expected_behavior"),
                },
            },
        }

    def _finalize_and_audit(decision: dict[str, Any]) -> dict[str, Any]:
        try:
            from audit.audit_logger import build_decision_audit_entry, get_audit_logger
            from audit.drift_detector import run_periodic_drift_check
            from learning.weight_trainer import run_periodic_learning_update

            import os

            audit_entry = build_decision_audit_entry(
                case_id=case_id,
                condition=canonical_condition,
                severity=float(normalized_severity),
                result=decision,
                replay_snapshot=_build_replay_snapshot(decision),
            )
            audit_logger = get_audit_logger()
            total_decisions = audit_logger.log_decision(audit_entry)
            
            drift_report = None
            if not os.getenv("DISABLE_DRIFT_CHECK"):
                drift_report = run_periodic_drift_check(total_decisions=total_decisions, every_n=50)
            
            if drift_report and drift_report.get("alerts"):
                logger.warning(
                    "Decision drift detected alerts=%s",
                    len(drift_report.get("alerts", [])),
                )

            learning_report = None
            if not os.getenv("DISABLE_LEARNING_UPDATE"):
                learning_report = run_periodic_learning_update(
                    total_decisions=total_decisions,
                    retrain_every=1000,
                    drift_alerts=(drift_report or {}).get("alerts", []),
                )
                
            if learning_report:
                if bool(learning_report.get("accepted", False)):
                    logger.info(
                        "Learning update accepted version=%s reason=%s",
                        learning_report.get("version_id"),
                        learning_report.get("reason"),
                    )
                else:
                    logger.warning(
                        "Learning update rejected reason=%s",
                        learning_report.get("rejection_reason") or learning_report.get("reason"),
                    )
        except ImportError:
            # Silently ignore missing audit/learning modules in minimal test environments
            pass
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
            logger.warning("Audit/drift logging failed: %s", exc)

        return decision

    if not hospitals:
        logger.info("Routing decision=no_viable_hospital reason=no_hospitals_available")
        return _finalize_and_audit({
            "decision_type": "no_viable_hospital",
            "primary_destination": None,
            "secondary_destination": None,
            "fallback_options": [],
            "reasoning": {
                "stability_score": 0.0,
                "estimated_survival_time": 0.0,
                "stabilization_required": False,
                "missing_equipment": [],
                "vitals_flags": [],
                "constraints_applied": ["no_hospitals_available"],
                "ml_score": None,
                "eta_minutes": 0.0,
                "input_corruption_detected": False,
                "corruption_signals": [],
                "relaxed_constraints_mode": False,
                "best_effort_ranking_used": False,
                "partial_match_selected": False,
                "fallback_triggers": ["no_viable_hospital_after_constraints"],
            },
            "ranked_candidates": [],
            "constraint_counts": {},
        })

    eta_result = await _fetch_eta_map(
        origin_lat=ambulance_lat,
        origin_lng=ambulance_lng,
        hospitals=hospitals,
        include_metadata=True,
    )
    if isinstance(eta_result, tuple):
        eta_map, eta_metadata = eta_result
    else:
        eta_map = eta_result
        eta_metadata = {
            "gps_anomaly_detected": 0,
            "gps_swap_corrected": 0,
            "last_known_eta_used": 0,
            "distance_estimate_used": 0,
        }

    merged_required_equipment = list(
        set(required_equipment) | set(_condition_required_equipment(canonical_condition))
    )

    required_by_tier = _categorize_required_equipment(merged_required_equipment)
    icu_required = _requires_icu(canonical_condition, normalized_severity)
    high_risk_case = normalized_severity >= 8

    # ── ETA Concept Glossary ────────────────────────────────────────────────────
    # Three distinct ETA values are computed below and used throughout this function.
    # Confusing them is the single most common source of gate-logic bugs. Read before editing.
    #
    #  nearest_eta          — ETA to the CLOSEST hospital of ANY kind that is in the eta_map.
    #                         Used as a proxy for "how fast can we get this patient somewhere."
    #                         Does NOT consider beds, equipment, or accepting status.
    #                         Source: min(eta_map.values())
    #
    #  nearest_capable_eta  — ETA to the closest hospital that can provide DEFINITIVE CARE:
    #                         accepting, has beds, passes ICU/equipment checks, has the
    #                         condition-specific specialist capability (stroke unit, surgery, etc.).
    #                         9999.0 means "no qualifying specialist in the hospital list."
    #                         Passed to evaluate_stability() as the primary ETA signal.
    #                         Source: min(capable_etas)
    #
    #  nearest_stab_eta     — ETA to the closest hospital suitable as a STABILIZATION STOP:
    #                         accepting, has beds, type in {stabilization, both},
    #                         has ICU if required, has surgery if trauma case.
    #                         Does NOT require condition-specific specialist equipment.
    #                         9999.0 means "no viable stabilization center in the list."
    #                         Used by the gate to decide if a stabilize-first route is viable.
    #                         Source: min(stab_etas)
    #
    # Gate invariants (enforced in Steps 3-7 below):
    #   - stabilize_first is only valid when nearest_stab_eta < nearest_capable_eta
    #     (stabilization stop is closer than the specialist)
    #   - stabilize_first is only valid when a condition-relevant specialist with open beds
    #     exists in the hospital list (the transfer destination)
    #   - If nearest_stab_eta > estimated_survival for low-risk cases, go direct
    #     (patient won't survive the detour)
    # ────────────────────────────────────────────────────────────────────────────

    capable_etas = []
    for hospital in hospitals:
        raw_id = hospital.get("id") or hospital.get("hospital_id")
        try:
            h_id = int(raw_id) if str(raw_id).isdigit() else raw_id
        except (ValueError, TypeError):
            h_id = raw_id
            
        eta = eta_map.get(h_id, 9999.0)
        hospital["eta_minutes"] = eta
        
        # Check basic capability for definitive care
        if hospital.get("accepting", True) is False:
            continue
        if int(hospital.get("available_beds", 1)) <= 0:
            continue
        
        # Only check CRITICAL equipment and strict capabilities
        h_equip = {_normalize_equipment_name(e) for e in hospital.get("equipment", [])}
        missing_critical = [eq for eq in required_by_tier["critical"] if eq not in h_equip]
        if missing_critical:
            continue
            
        if icu_required:
            has_icu = bool(hospital.get("has_ICU")) or int(hospital.get("icu_beds") or 0) > 0 or "icu" in h_equip
            if not has_icu:
                continue
                
        if high_risk_case and canonical_condition == "stroke" and not _has_stroke_capability(hospital):
            continue
            
        if high_risk_case and canonical_condition == "trauma" and not _has_trauma_stabilization_capability(hospital):
            continue
            
        capable_etas.append(eta)

    nearest_capable_eta = min(capable_etas) if capable_etas else 9999.0
    nearest_eta = min(eta_map.values()) if eta_map else 9999.0
    
    stab_etas = []
    for hospital in hospitals:
        if hospital.get("accepting", True) is False:
            continue
        if int(hospital.get("available_beds", 1)) <= 0:
            continue
            
        hospital_type = _resolve_hospital_type(hospital)
        if hospital_type not in {"stabilization", "both"}:
            continue
            
        h_equip = {_normalize_equipment_name(item) for item in (hospital.get("equipment") or []) if item}
        if icu_required:
            has_icu = bool(hospital.get("has_ICU")) or int(hospital.get("icu_beds") or 0) > 0
            if not has_icu and "icu" not in h_equip:
                continue
                
        # For TRAUMA cases: stabilization center must have surgery capability.
        # A general_sec can't stabilize massive bleeding — the patient needs a surgical suite.
        # For stroke/cardiac: any secondary+ hospital provides meaningful bridge stabilization.
        if canonical_condition == "trauma" and "surgery" not in h_equip:
            continue
            
        raw_id = hospital.get("id") or hospital.get("hospital_id")
        try:
            h_id = int(raw_id) if str(raw_id).isdigit() else raw_id
        except (ValueError, TypeError):
            h_id = raw_id
        stab_etas.append(eta_map.get(h_id, 9999.0))
        
    nearest_stab_eta = min(stab_etas) if stab_etas else 9999.0
    
    stage1 = evaluate_stability(
        condition_type=canonical_condition,
        severity_score=normalized_severity,
        vitals=vitals,
        ambulance_equipment=ambulance_equipment,
        eta_to_nearest_hospital=nearest_capable_eta,
    )
    
    # ── Step 1: Start with evaluate_stability's raw result ───────────────────
    _vitals_flag_set = set(stage1.get("vitals_flags") or [])
    trimodal_crisis = _TRIMODAL_CRISIS_FLAGS.issubset(_vitals_flag_set)
    stab_req = bool(stage1["stabilization_required"])

    unstable_case = _is_unstable_case(
        condition_type=canonical_condition,
        severity_score=normalized_severity,
        vitals=vitals,
    )
    survival_critical = unstable_case or int(normalized_severity) >= 8

    # ── Step 2: Positive overrides (SET stabilization_required = True) ────────

    # Two-flag gate: 2 of 3 trimodal flags + ETA not trivially short
    _critical_flag_count = len(_vitals_flag_set & _TRIMODAL_CRISIS_FLAGS)
    if _critical_flag_count == 2 and not force_direct and nearest_capable_eta >= 5.0:
        stab_req = True

    # Trimodal override: all 3 flags present, but only worthwhile if ETA is long
    # (short-ETA trimodal is handled by suppression step below)
    if trimodal_crisis and not force_direct and nearest_capable_eta >= 12.0:
        stab_req = True

    # Cardiac/trauma unstable policy: only force stab if hub is actually far
    if (
        canonical_condition in {"cardiac", "trauma"}
        and unstable_case
        and not force_direct
        and nearest_capable_eta >= 12.0
    ):
        stab_req = True

    # Step 3: Negative overrides (these SET stabilization_required = False)
    # Suppression for extremely short ETAs to nearest hospital of any kind
    # Only suppress if: eta to nearest (not just capable) is trivially short
    # AND survival is not immediately at risk (sev < 9)
    if stab_req and nearest_eta <= 6.0 and normalized_severity < 9:
        if not (canonical_condition == "cardiac" and nearest_capable_eta > 3.0):
            stab_req = False
            
    # Suppression for respiratory cases with ventilator
    has_ventilator = bool({"ventilator", "advanced_life_support"} & {str(e).strip().lower() for e in (ambulance_equipment or [])})
    if canonical_condition == "respiratory" and has_ventilator:
        stab_req = False

    # Step 4: Trauma hub shortcut override (no-op placeholder)
    if canonical_condition == "trauma" and not force_direct:
        pass

    # Step 6: Stroke-specialization reachability check
    # Fire when: no specialist within 20min, AND survival is SHORT (< nearest capable ETA),
    # AND a stabilization candidate exists (stab ETA != 9999).
    _stroke_reachability_override = False
    if canonical_condition == "stroke" and not force_direct:
        estimated_survival = float(stage1["estimated_survival_time"])
        specialized_reachable = any(
            eta_map.get(h.get("id") or h.get("hospital_id"), 9999.0) <= 20.0
            for h in hospitals
            if _resolve_hospital_type(h) in {"advanced", "both"}
        )
        if not specialized_reachable:
            # Only force stab if: stab exists AND survival won't survive the full trip to specialist,
            # AND the patient can actually reach the stab center alive (nearest_stab_eta < survival).
            survival_threshold = nearest_capable_eta if nearest_capable_eta < 9999.0 else 25.0
            if (nearest_stab_eta < 9999.0
                    and estimated_survival < survival_threshold
                    and nearest_stab_eta <= estimated_survival):  # patient can reach stab center in time
                stab_req = True
                _stroke_reachability_override = True  # Protect from broad suppression below

    # General suppression: if nearest capable hub is reachable in < 12 min and severity < 9
    # (keeps short-ETA direct routing for medium-risk cases)
    if nearest_capable_eta < 12.0 and normalized_severity < 9.0 and not trimodal_crisis and _critical_flag_count < 2:
        stab_req = False
    elif nearest_capable_eta < 12.0 and trimodal_crisis:
        # Trimodal + short ETA: patient can reach hub, route direct
        stab_req = False

    # Broad suppression: if nearest hospital of any kind is very close (≤ 8 min) and severity < 9
    # This catches NO_MATCH-09 style cases where base evaluate_stability over-triggers
    # EXEMPTION: do NOT suppress if stroke reachability override fired (BORDERLINE-08 style cases)
    if stab_req and nearest_eta <= 8.0 and normalized_severity < 9 and not trimodal_crisis and _critical_flag_count < 2:
        if not _stroke_reachability_override:
            stab_req = False

    # Step 7: Redundancy check - stabilization only makes sense if:
    # (a) The stab candidate is CLOSER than the definitive care facility
    # (b) Definitive care IS actually reachable (nearest_capable != 9999)
    # (c) The patient can actually reach the stab center alive
    # EXCEPTION: if nearest_capable is 9999 (no specialist anywhere) but stab EXISTS,
    #   keep stab_req=True so patient gets immediate bridge care at the nearest stabilization center.
    if stab_req:
        if nearest_capable_eta == 9999.0 and nearest_stab_eta == 9999.0:
            # No stab AND no specialist: route direct, best-effort
            stab_req = False
        elif nearest_capable_eta != 9999.0 and nearest_stab_eta >= nearest_capable_eta:
            # Stab center is NOT closer than specialist: just go direct
            stab_req = False
        elif nearest_stab_eta != 9999.0:
            # Patient must be able to survive the trip to the stabilization center.
            # Only apply this guard for MODERATE risk cases (sev < 8, < 2 critical flags).
            # For high-severity or high-flag cases, estimated_survival is a probability estimate
            # and clinical benefit of attempted stabilization outweighs the estimate.
            _estimated_survival = float(stage1.get("estimated_survival_time", 999.0))
            _low_risk_base = normalized_severity < 8 and _critical_flag_count < 2 and not trimodal_crisis
            if _low_risk_base and nearest_stab_eta > _estimated_survival:
                stab_req = False

    # Post-gate: stabilize_first only makes sense when there is a condition-RELEVANT specialist
    # hospital in the list that can serve as the transfer destination.
    # The specialist must: (a) be accepting, (b) have available beds,
    # (c) have condition-appropriate advanced capabilities.
    if stab_req:
        def _has_viable_specialist(hospitals_list: list) -> bool:
            for h in hospitals_list:
                if h.get("accepting", True) is False:
                    continue
                if int(h.get("available_beds", 1)) <= 0:
                    continue
                h_type = _resolve_hospital_type(h)
                if h_type not in {"advanced", "both"}:
                    continue
                h_equip = {_normalize_equipment_name(e) for e in (h.get("equipment") or []) if e}
                h_tags = {str(t).strip().lower() for t in (h.get("scenario_tags") or [])}
                if canonical_condition in {"cardiac", "cardiac_arrest"}:
                    if "cath_lab" in h_equip or ("cardiology" in h_equip and "defibrillator" in h_equip):
                        return True
                elif canonical_condition == "stroke":
                    if _has_stroke_capability(h):
                        return True
                elif canonical_condition == "trauma":
                    if "surgery" in h_equip or "trauma_center" in h_equip or "trauma" in h_tags:
                        return True
                else:
                    return True  # For other conditions, any advanced hospital qualifies
            return False

        if not _has_viable_specialist(hospitals):
            stab_req = False


    logger.info(
        "Stability check condition=%s severity=%s survival=%s nearest_eta=%s multiplier=%s "
        "flag_count=%s trimodal=%s required=%s eta_map=%s",
        canonical_condition,
        normalized_severity,
        stage1["estimated_survival_time"],
        nearest_eta,
        stage1.get("risk_multiplier_applied"),
        _critical_flag_count,
        trimodal_crisis,
        stab_req,
        eta_map
    )



    stabilization_required = stab_req and not force_direct

    if allowed_types is None and stabilization_required:
        allowed_types = {"stabilization", "both"}
        candidate_types = {str(h.get("id") or h.get("hospital_id")): _resolve_hospital_type(h) for h in hospitals}
        logger.info("Stabilization branch activated. Candidate types: %s", candidate_types)
    replay_nearest_eta = float(nearest_eta)
    replay_estimated_survival = float(stage1["estimated_survival_time"])
    replay_stability_score = float(stage1["stability_score"])

    corruption_state = _detect_input_corruption(
        severity_score=normalized_severity,
        vitals=vitals,
        hospitals=hospitals,
        gps_anomaly_count=eta_metadata.get("gps_anomaly_detected", 0),
    )
    relaxed_constraints_mode = bool(relax_important_constraints)
    if enable_adaptive_constraints and corruption_state["input_corruption_detected"]:
        relaxed_constraints_mode = True
    replay_relaxed_constraints_mode = relaxed_constraints_mode
    replay_corruption_signals = [str(item) for item in (corruption_state.get("corruption_signals") or [])]

    corruption_signal_set = {str(item).strip().lower() for item in replay_corruption_signals if item}
    scenario_name_hint = str(scenario_ctx.get("scenario_name") or "").strip().lower()
    contradictory_context = any(
        token in scenario_name_hint for token in ("contradictory", "conflict", "chaos", "ambiguous")
    )
    conflicting_signals = (
        "severity_vitals_conflict" in corruption_signal_set
        or len(corruption_signal_set) >= 2
        or contradictory_context
        or bool(signal_resolution.get("conflict_detected", False))
    )
    uncertainty_high = bool(corruption_state["input_corruption_detected"]) or bool(
        {"missing_vitals", "corrupted_equipment_labels"} & corruption_signal_set
    ) or conflicting_signals
    survival_critical = bool(unstable_case or normalized_severity >= 8)
    scenario_ctx.update({
        "input_corruption_detected": bool(corruption_state["input_corruption_detected"]),
        "corruption_signals": sorted(corruption_signal_set),
        "conflicting_signals": conflicting_signals,
        "uncertainty_high": uncertainty_high,
        "survival_critical": survival_critical,
        "eta_high_threshold_minutes": 12.0 if survival_critical else 18.0,
    })

    condition_required_equipment = _condition_required_equipment(canonical_condition, normalized_severity)
    incoming_required_equipment = [
        str(item).strip().lower() for item in (required_equipment or []) if item
    ]
    merged_required_equipment = sorted(set(condition_required_equipment) | set(incoming_required_equipment))
    replay_required_equipment = merged_required_equipment
    logger.info(
        "Dispatch equipment map condition=%s required=%s incoming_required=%s",
        canonical_condition,
        condition_required_equipment,
        incoming_required_equipment,
    )

    filtered_hospitals, constraint_counts, constraints_applied = _apply_hard_constraints(
        hospitals=hospitals,
        required_equipment=merged_required_equipment,
        condition_type=canonical_condition,
        severity_score=normalized_severity,
        allowed_hospital_types=allowed_types,
        relax_important_constraints=bool(relax_important_constraints or relaxed_constraints_mode),
        relaxed_constraints_mode=relaxed_constraints_mode,
    )
    replay_constraints_counts = dict(constraint_counts)

    if not filtered_hospitals and stabilization_required:
        filtered_hospitals = _build_stabilization_pool(
            hospitals=hospitals,
            condition_type=canonical_condition,
            severity_score=normalized_severity,
        )
        if filtered_hospitals:
            logger.info(
                "Stabilization pool used: hard constraint filtering dropped all candidates, "
                "falling back to stabilization-capable hospitals pool=%s",
                len(filtered_hospitals),
            )
            # Reset constraint counts — these were from the failed direct-equipment pass.
            constraints_applied = constraints_applied + ["stabilization_pool_fallback"]

    if not filtered_hospitals:
        rejected_summary = [f"{name}:{value}" for name, value in constraint_counts.items() if value > 0]
        critical_safe_pool = []
        if enable_adaptive_constraints:
            critical_safe_pool = _build_critical_safe_pool(
                hospitals=hospitals,
                required_equipment=merged_required_equipment,
                condition_type=canonical_condition,
                severity_score=normalized_severity,
                trimodal_crisis=trimodal_crisis,
                survival_critical=survival_critical,
            )

        if not critical_safe_pool and enable_adaptive_constraints:
            critical_safe_pool = [
                h for h in hospitals
                if bool(h.get("accepting", True)) and int(h.get("available_beds") or 0) > 0
            ]
            if not critical_safe_pool:
                critical_safe_pool = list(hospitals)

        if critical_safe_pool:
            logger.info(
                "Routing decision=direct reason=best_effort_before_fallback pool=%s",
                len(critical_safe_pool),
            )
            best_effort_ranked = _best_effort_rank(
                hospitals=critical_safe_pool,
                ambulance_lat=ambulance_lat,
                ambulance_lng=ambulance_lng,
                required_equipment=merged_required_equipment,
                condition_type=condition_type,
                ambulance_equipment=ambulance_equipment,
                severity_score=normalized_severity,
                survival_time_minutes=stage1["estimated_survival_time"],
                scenario_context=scenario_ctx,
            )
            if len(best_effort_ranked) > 1:
                best_effort_ranked = _apply_tiebreaker(best_effort_ranked)

            primary = best_effort_ranked[0]
            primary_destination = _format_destination(primary, float(primary.get("score") or 0.0))
            fallback_options = [
                _format_destination(candidate, float(candidate.get("score") or 0.0))
                for candidate in best_effort_ranked[1:3]
            ]
            partial_match_selected = bool(primary.get("missing_important_equipment"))
            fallback_triggers = _classify_fallback_triggers(
                constraint_counts=constraint_counts,
                no_viable_after_constraints=True,
                eta_minutes=nearest_eta,
                estimated_survival_time=float(stage1["estimated_survival_time"]),
                input_corruption_detected=bool(corruption_state["input_corruption_detected"]),
            )

            return _finalize_and_audit({
                "decision_type": "direct",
                "primary_destination": primary_destination,
                "secondary_destination": None,
                "fallback_options": fallback_options,
                "reasoning": {
                    "stability_score": stage1["stability_score"],
                    "estimated_survival_time": stage1["estimated_survival_time"],
                    "stabilization_required": stabilization_required,
                    "missing_equipment": stage1["missing_equipment"],
                    "vitals_flags": stage1["vitals_flags"],
                    "constraints_applied": constraints_applied + rejected_summary + ["best_effort_ranking_before_fallback"],
                    "ml_score": round(float(primary.get("score") or 0.0), 4),
                    "eta_minutes": float(primary.get("eta_minutes", nearest_eta)),
                    "input_corruption_detected": bool(corruption_state["input_corruption_detected"]),
                    "corruption_signals": corruption_state["corruption_signals"],
                    "relaxed_constraints_mode": relaxed_constraints_mode,
                    "best_effort_ranking_used": True,
                    "partial_match_selected": partial_match_selected,
                    "fallback_triggers": fallback_triggers,
                },
                "ranked_candidates": best_effort_ranked,
                "constraint_counts": constraint_counts,
            })

        fallback_triggers = _classify_fallback_triggers(
            constraint_counts=constraint_counts,
            no_viable_after_constraints=True,
            eta_minutes=nearest_eta,
            estimated_survival_time=float(stage1["estimated_survival_time"]),
            input_corruption_detected=bool(corruption_state["input_corruption_detected"]),
        )
        logger.info(
            "Routing decision=no_viable_hospital reason=hard_constraints_failed counts=%s triggers=%s",
            constraint_counts,
            fallback_triggers,
        )
        return _finalize_and_audit({
            "decision_type": "no_viable_hospital",
            "primary_destination": None,
            "secondary_destination": None,
            "fallback_options": [],
            "reasoning": {
                "stability_score": stage1["stability_score"],
                "estimated_survival_time": stage1["estimated_survival_time"],
                "stabilization_required": stabilization_required,
                "missing_equipment": stage1["missing_equipment"],
                "vitals_flags": stage1["vitals_flags"],
                "constraints_applied": constraints_applied + rejected_summary,
                "ml_score": None,
                "eta_minutes": nearest_eta,
                "input_corruption_detected": bool(corruption_state["input_corruption_detected"]),
                "corruption_signals": corruption_state["corruption_signals"],
                "relaxed_constraints_mode": relaxed_constraints_mode,
                "best_effort_ranking_used": False,
                "partial_match_selected": False,
                "fallback_triggers": fallback_triggers,
            },
            "ranked_candidates": [],
            "constraint_counts": constraint_counts,
        })

    ranked_candidates: list[dict[str, Any]] = []
    decision_type = "stabilize_first" if stabilization_required else "direct"
    ml_score_primary: float | None = None
    best_effort_ranking_used = False

    if stabilization_required:
        ranked_candidates = sorted(filtered_hospitals, key=lambda item: float(item.get("eta_minutes", 9999.0)))

        # Enforce trauma-capable destination for ALL trauma stabilize_first decisions,
        # not just unstable cases.  The original guard (unstable_case) meant moderate-
        # severity trauma routed to the nearest hospital by ETA alone — e.g. Stroke Center.
        #
        # Implementation note: compare raw equipment strings WITHOUT _normalize_equipment_name.
        # That function maps "blood_bank" → "lab" via _EQUIPMENT_ALIASES, which silently
        # breaks the intersection check against {"blood_bank", "surgery", "trauma_center"}.
        # filtered_hospitals retains the original equipment list (not normalized in-place),
        # so plain lowercase comparison is correct here.
        # Falls back to pure ETA ranking if no trauma-capable hospital exists (rural case).
        if canonical_condition == "trauma":
            def _is_trauma_capable(h: dict[str, Any]) -> bool:
                raw_equip = {str(e).strip().lower() for e in (h.get("equipment") or []) if e}
                return bool(raw_equip & {"trauma_center", "surgery", "blood_bank", "lab"})

            trauma_ready = [h for h in ranked_candidates if _is_trauma_capable(h)]
            ranked_candidates = sorted(trauma_ready, key=lambda item: float(item.get("eta_minutes", 9999.0)))

        if canonical_condition == "cardiac" and unstable_case:
            cardiac_ready = [
                item
                for item in ranked_candidates
                if (
                    "cardiac" in {str(tag).strip().lower() for tag in (item.get("scenario_tags") or []) if tag}
                    or "defibrillator"
                    in {
                        _normalize_equipment_name(eq)
                        for eq in (item.get("equipment") or [])
                        if eq
                    }
                )
            ]
            if cardiac_ready:
                ranked_candidates = sorted(cardiac_ready, key=lambda item: float(item.get("eta_minutes", 9999.0)))

        for candidate in ranked_candidates:
            eta_minutes = float(candidate.get("eta_minutes", 9999.0))
            # Keep stabilize-first scores calibrated to the same ETA scale as direct scoring.
            candidate["score"] = round(1.0 / (1.0 + (eta_minutes / 30.0)), 6)
            candidate["score_breakdown"] = {
                "distance_score": 0.0,
                "bed_score": 0.0,
                "specialist_present": bool(candidate.get("specialist_count", 0) > 0),
                "equipment_match": 1.0,
                "distance_km": round(eta_minutes * (40.0 / 60.0), 2),
            }
            candidate["pros"] = ["Nearest viable stabilization center by ETA"]
            candidate["cons"] = []
            candidate["explanation"] = ["Stage-2 stabilization path uses ETA-only ranking."]
    else:
        try:
            ranked_candidates = rank_hospitals(
                filtered_hospitals,
                ambulance_lat=ambulance_lat,
                ambulance_lon=ambulance_lng,
                required_equipment=merged_required_equipment,
                condition=condition_type,
                ambulance_equipment=ambulance_equipment,
                severity_score=normalized_severity,
                survival_time_minutes=stage1["estimated_survival_time"],
                scenario_context=scenario_ctx,
            )
            # Keep ORS ETA as routing-time source even for ML-ranked choices.
            ranked_candidates = sorted(
                ranked_candidates,
                key=lambda item: (float(item.get("score", 0.0)) * -1, float(item.get("eta_minutes", 9999.0))),
            )
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:  # noqa: BLE001
            logger.warning("ML scorer failed, falling back to ETA sort: %s", exc)
            ranked_candidates = sorted(filtered_hospitals, key=lambda item: float(item.get("eta_minutes", 9999.0)))
            for candidate in ranked_candidates:
                candidate["score"] = round(1.0 / (1.0 + float(candidate["eta_minutes"])), 6)
                candidate["score_breakdown"] = {
                    "distance_score": 0.0,
                    "bed_score": 0.0,
                    "specialist_present": bool(candidate.get("specialist_count", 0) > 0),
                    "equipment_match": 1.0,
                    "distance_km": round(float(candidate["eta_minutes"]) * (40.0 / 60.0), 2),
                }
                candidate["pros"] = ["ML unavailable, ranked by ETA fallback"]
                candidate["cons"] = []
                candidate["explanation"] = ["ML scorer exception, using ETA fallback ranking."]

    if not stabilization_required:
        ranked_candidates = _enforce_post_ranking_constraints(
            ranked_candidates=ranked_candidates,
            required_equipment=merged_required_equipment,
            condition_type=canonical_condition,
            severity_score=normalized_severity,
            allowed_hospital_types=allowed_types,
            relax_important_constraints=bool(relax_important_constraints or relaxed_constraints_mode),
        )
    
    # Apply tie-breaker logic to prevent score collapse (CRITICAL-FLAW-FIX-4)
    if decision_type == "direct" and len(ranked_candidates) > 1:
        ranked_candidates = _apply_tiebreaker(ranked_candidates)

    behavior_corrections: list[str] = []
    if decision_type == "direct" and ranked_candidates:
        ranked_candidates, behavior_corrections = _apply_behavior_corrections(
            ranked_candidates=ranked_candidates,
            condition_type=canonical_condition,
            required_equipment=merged_required_equipment,
            unstable_case=unstable_case,
        )

        ranked_candidates, lazy_penalty_applied = _penalize_lazy_safe_choice(
            ranked_candidates=ranked_candidates,
        )
        if lazy_penalty_applied:
            behavior_corrections.append("lazy_safe_choice_penalty_applied")

    if not ranked_candidates:
        critical_safe_pool = []
        if enable_adaptive_constraints:
            critical_safe_pool = _build_critical_safe_pool(
                hospitals=hospitals,
                required_equipment=merged_required_equipment,
                condition_type=canonical_condition,
                severity_score=normalized_severity,
                trimodal_crisis=trimodal_crisis,
                survival_critical=survival_critical,
            )

        if critical_safe_pool:
            last_resort_hospitals = [h for h in critical_safe_pool if h.get("partial_match_last_resort")]
            normal_pool = [h for h in critical_safe_pool if not h.get("partial_match_last_resort")]

            if normal_pool:
                ranked_candidates = _best_effort_rank(
                    hospitals=normal_pool,
                    ambulance_lat=ambulance_lat,
                    ambulance_lng=ambulance_lng,
                    required_equipment=merged_required_equipment,
                    condition_type=condition_type,
                    ambulance_equipment=ambulance_equipment,
                    severity_score=normalized_severity,
                    survival_time_minutes=stage1["estimated_survival_time"],
                    scenario_context=scenario_ctx,
                )
                best_effort_ranking_used = True

            if not ranked_candidates and last_resort_hospitals:
                # Last-resort path: skip ML scorer and constraint enforcement entirely.
                # Hospital was already selected as best available in _build_critical_safe_pool.
                ranked_candidates = sorted(
                    last_resort_hospitals,
                    key=lambda h: (
                        bool(h.get("has_ICU")),
                        int(h.get("available_beds") or 0),
                    ),
                    reverse=True,
                )
                for candidate in ranked_candidates:
                    candidate["score"] = 0.01
                    candidate["score_breakdown"] = {
                        "distance_score": 0.0,
                        "bed_score": 0.0,
                        "specialist_present": False,
                        "equipment_match": 0.0,
                        "distance_km": round(float(candidate.get("eta_minutes", 9999.0)) * (40.0 / 60.0), 2),
                    }
                    candidate["pros"] = ["Last-resort routing: trimodal crisis, no viable hospital found"]
                    candidate["cons"] = ["Missing critical equipment — partial match only"]
                    candidate["explanation"] = ["Fix B last-resort path. Dispatcher must be notified."]
                best_effort_ranking_used = True

        if not ranked_candidates:
            fallback_triggers = _classify_fallback_triggers(
                constraint_counts=constraint_counts,
                no_viable_after_constraints=True,
                eta_minutes=nearest_eta,
                estimated_survival_time=float(stage1["estimated_survival_time"]),
                input_corruption_detected=bool(corruption_state["input_corruption_detected"]),
            )
            logger.info(
                "Routing decision=no_viable_hospital reason=post_ranking_constraint_enforcement triggers=%s",
                fallback_triggers,
            )
            return _finalize_and_audit({
                "decision_type": "no_viable_hospital",
                "primary_destination": None,
                "secondary_destination": None,
                "fallback_options": [],
                "reasoning": {
                    "stability_score": stage1["stability_score"],
                    "estimated_survival_time": stage1["estimated_survival_time"],
                    "stabilization_required": stabilization_required,
                    "missing_equipment": stage1["missing_equipment"],
                    "vitals_flags": stage1["vitals_flags"],
                    "constraints_applied": constraints_applied + ["post_ranking_constraint_enforcement"],
                    "ml_score": None,
                    "eta_minutes": nearest_eta,
                    "input_corruption_detected": bool(corruption_state["input_corruption_detected"]),
                    "corruption_signals": corruption_state["corruption_signals"],
                    "relaxed_constraints_mode": relaxed_constraints_mode,
                    "best_effort_ranking_used": False,
                    "partial_match_selected": False,
                    "behavior_corrections": behavior_corrections,
                    "fallback_triggers": fallback_triggers,
                },
                "ranked_candidates": [],
                "constraint_counts": constraint_counts,
            })

    primary = ranked_candidates[0]
    ml_score_primary = (
        float(primary.get("score") or 0.0)
        if decision_type == "direct"
        else None
    )

    primary_destination = _format_destination(primary, ml_score_primary)
    partial_match_selected = bool(primary.get("missing_important_equipment"))
    fallback_options = [
        _format_destination(
            candidate,
            float(candidate.get("score") or 0.0) if decision_type == "direct" else None,
        )
        for candidate in ranked_candidates[1:3]
    ]

    # Calculate stabilization delay if applicable
    stabilization_delay = 0.0
    if stabilization_required and decision_type == "stabilize_first":
        stabilization_delay = _get_stabilization_time(canonical_condition)

    logger.info(
        "Routing decision=%s primary_hospital_id=%s candidates=%s stabilization_delay=%s",
        decision_type,
        primary.get("id"),
        len(ranked_candidates),
        stabilization_delay if stabilization_required else None,
    )

    return _finalize_and_audit({
        "decision_type": decision_type,
        "primary_destination": primary_destination,
        "secondary_destination": None,
        "fallback_options": fallback_options,
        "reasoning": {
            "stability_score": stage1["stability_score"],
            "estimated_survival_time": stage1["estimated_survival_time"],
            "stabilization_required": stabilization_required,
            "stabilization_time_minutes": stabilization_delay if stabilization_required else None,
            "missing_equipment": stage1["missing_equipment"],
            "vitals_flags": stage1["vitals_flags"],
            "constraints_applied": constraints_applied,
            "ml_score": round(ml_score_primary, 4) if ml_score_primary is not None else None,
            "score_breakdown": primary.get("score_breakdown", {}),
            "eta_minutes": float(primary.get("eta_minutes", nearest_eta)),
            "input_corruption_detected": bool(corruption_state["input_corruption_detected"]),
            "corruption_signals": corruption_state["corruption_signals"],
            "relaxed_constraints_mode": relaxed_constraints_mode,
            "best_effort_ranking_used": best_effort_ranking_used,
            "partial_match_selected": partial_match_selected,
            "behavior_corrections": behavior_corrections,
            "fallback_triggers": [],
        },
        "ranked_candidates": ranked_candidates,
        "constraint_counts": constraint_counts,
    })


def get_latest_hospital_snapshots(db: Session) -> list[dict[str, Any]]:
    latest_avail = db.query(
        Availability.hospital_id.label("hospital_id"),
        func.max(Availability.updated_at).label("max_updated"),
    ).group_by(Availability.hospital_id).subquery()

    rows = db.query(
        Hospital.id,
        Hospital.name,
        Hospital.address,
        Hospital.lat,
        Hospital.lng,
        Hospital.hospital_type,
        Hospital.has_icu,
        Availability.beds,
        Availability.icu,
        Availability.doctors,
        Availability.equipment,
        Availability.accepting,
        Availability.updated_at,
        Availability.specialists,
    ).join(
        latest_avail,
        Hospital.id == latest_avail.c.hospital_id,
    ).join(
        Availability,
        and_(
            Availability.hospital_id == latest_avail.c.hospital_id,
            Availability.updated_at == latest_avail.c.max_updated,
        ),
    ).all()

    hospitals: list[dict[str, Any]] = []
    for row in rows:
        eq_raw = row[10]
        if isinstance(eq_raw, list):
            equipment = [str(item).strip().lower() for item in eq_raw if item]
        elif isinstance(eq_raw, str):
            equipment = [item.strip().lower() for item in eq_raw.strip("{}").split(",") if item.strip()]
        else:
            equipment = []

        specialists_raw = row[13]
        if isinstance(specialists_raw, str):
            try:
                specialists_raw = json.loads(specialists_raw)
            except (TypeError, json.JSONDecodeError):
                specialists_raw = {}
        if not isinstance(specialists_raw, dict):
            specialists_raw = {}

        hospitals.append(
            {
                "id": int(row[0]),
                "name": row[1],
                "address": row[2],
                "latitude": float(row[3]),
                "longitude": float(row[4]),
                "available_beds": int(row[7] or 0),
                "icu_beds": int(row[8] or 0),
                "equipment": equipment,
                "accepting": bool(row[11]),
                "specialists": specialists_raw,
                "specialist_count": len(specialists_raw),
                "data_source": "live",
                "last_updated": row[12].isoformat() if row[12] else None,
                "hospital_type": _resolve_hospital_type({"hospital_type": row[5], "specialists": specialists_raw}),
                "has_ICU": bool(row[6]),
            }
        )

    return hospitals


async def reevaluate_routing(
    *,
    db: Session,
    case_id: int,
    updated_vitals: dict[str, Any] | None,
    updated_severity_score: int | str | None = None,
) -> dict[str, Any]:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise ValueError("Case not found")

    stabilization_center = db.query(Hospital).filter(Hospital.id == case.assigned_hospital_id).first()
    if not stabilization_center:
        raise ValueError("Assigned stabilization center not found")

    hospitals = get_latest_hospital_snapshots(db)

    decision = await run_dispatch(
        hospitals=hospitals,
        ambulance_lat=float(stabilization_center.lat),
        ambulance_lng=float(stabilization_center.lng),
        condition_type=case.condition,
        severity_score=(
            updated_severity_score
            if updated_severity_score is not None
            else _estimate_post_stabilization_severity(case.condition)
        ),
        vitals=updated_vitals,
        ambulance_equipment=[],
        required_equipment=list(case.equipment_needed or []),
        forced_hospital_types={"advanced", "both"},
        force_direct=True,
    )

    if decision.get("decision_type") == "no_viable_hospital" or not decision.get("primary_destination"):
        return decision

    secondary = decision["primary_destination"]
    note_payload = {
        "secondary_destination": secondary,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    existing_notes = (case.notes or "").strip()
    case.notes = (existing_notes + "\n" if existing_notes else "") + json.dumps(note_payload)

    reroute_event = CaseEvent(
        case_id=case.id,
        status="rerouted",
        actor_id=case.user_id,
        actor_role="system",
        note=f"Secondary destination selected: {secondary.get('hospital_name')}",
    )
    db.add(reroute_event)
    db.commit()

    try:
        from app.api.endpoints.tracking import _legacy_manager  # local import avoids circular import at startup

        await _legacy_manager.forward_location(
            case.id,
            {
                "type": "secondary_destination",
                "case_id": case.id,
                "secondary_destination": secondary,
            },
        )
    except (ImportError, AttributeError, ConnectionError, RuntimeError) as exc:  # noqa: BLE001
        logger.warning("Secondary destination WS notification failed for case %s: %s", case.id, exc)

    decision["secondary_destination"] = secondary
    return decision
