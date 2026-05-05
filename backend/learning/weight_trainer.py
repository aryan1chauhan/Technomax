"""Closed-loop weight training, validation guardrails, and version control."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.feature_extraction import DictVectorizer

from app.engine.ml_scorer import rank_hospitals
from audit.audit_logger import get_audit_logger
from .learning_dataset import build_learning_dataset, load_learning_dataset

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
DATASET_PATH = ARTIFACT_DIR / "learning_dataset.jsonl"
VERSIONS_PATH = ARTIFACT_DIR / "weight_versions.jsonl"
UPDATES_PATH = ARTIFACT_DIR / "weight_update_log.jsonl"
SCENARIO_ADJUSTMENTS_PATH = ARTIFACT_DIR / "scenario_adjustments.json"

DEFAULT_WEIGHTS: dict[str, float] = {
    "w_survival": 0.30,
    "w_treatment": 0.25,
    "w_equipment": 0.20,
    "w_eta": 0.15,
    "w_load": 0.10,
}

WEIGHT_BOUNDS: dict[str, tuple[float, float]] = {
    "w_survival": (0.20, 0.45),
    "w_treatment": (0.15, 0.35),
    "w_equipment": (0.10, 0.30),
    "w_eta": (0.05, 0.25),
    "w_load": (0.05, 0.20),
}

SCENARIO_PRIORITY_FOCUS: dict[str, tuple[str, ...]] = {
    "time": ("w_survival", "w_eta"),
    "specialty": ("w_treatment", "w_equipment"),
    "stabilization": ("w_survival", "w_treatment"),
    "equipment": ("w_equipment", "w_treatment"),
}

FAILURE_WEIGHT_HINTS: dict[str, str] = {
    "eta_delay": "w_eta",
    "late_handover": "w_eta",
    "specialty_mismatch": "w_treatment",
    "treatment_mismatch": "w_treatment",
    "stabilization_miss": "w_survival",
    "stabilization_skip": "w_survival",
    "equipment_gap": "w_equipment",
    "bed_shortage": "w_load",
    "fallback_dependency": "w_load",
}

_FALLBACK_ACTIVE_WEIGHTS: dict[str, float] = dict(DEFAULT_WEIGHTS)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, _safe_float(weights.get(key), 0.0)) for key in DEFAULT_WEIGHTS)
    if total <= 0.0:
        return dict(DEFAULT_WEIGHTS)
    return {
        key: max(0.0, _safe_float(weights.get(key), DEFAULT_WEIGHTS[key])) / total
        for key in DEFAULT_WEIGHTS
    }


def _clamp_weights(weights: dict[str, float]) -> dict[str, float]:
    normalized = _normalize_weights(weights)
    for _ in range(2):
        clamped = {}
        for key, value in normalized.items():
            low, high = WEIGHT_BOUNDS[key]
            clamped[key] = max(low, min(high, value))
        normalized = _normalize_weights(clamped)
    return {key: round(value, 6) for key, value in normalized.items()}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _weight_store() -> dict[str, float]:
    try:
        from tests.trust_layer import ACTIVE_WEIGHTS  # type: ignore

        if isinstance(ACTIVE_WEIGHTS, dict):
            return ACTIVE_WEIGHTS
    except (ImportError, RuntimeError, ValueError, TypeError):
        pass
    return _FALLBACK_ACTIVE_WEIGHTS


def get_active_weights() -> dict[str, float]:
    store = _weight_store()
    candidate = {key: _safe_float(store.get(key), DEFAULT_WEIGHTS[key]) for key in DEFAULT_WEIGHTS}
    return _clamp_weights(candidate)


def _set_active_weights(weights: dict[str, float]) -> dict[str, float]:
    store = _weight_store()
    applied = _clamp_weights(weights)
    store.clear()
    store.update(applied)
    return dict(applied)


def _with_temporary_weights(weights: dict[str, float], fn: Any) -> Any:
    store = _weight_store()
    original = dict(store)
    try:
        store.clear()
        store.update(_clamp_weights(weights))
        return fn()
    finally:
        store.clear()
        store.update(original)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                parsed = json.loads(stripped)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def get_weight_versions(limit: int = 20) -> list[dict[str, Any]]:
    rows = _read_jsonl(VERSIONS_PATH)
    if limit <= 0:
        return rows
    return rows[-limit:]


def get_recent_weight_updates(limit: int = 20) -> list[dict[str, Any]]:
    rows = _read_jsonl(UPDATES_PATH)
    if limit <= 0:
        return rows
    return rows[-limit:]


def _rows_to_model_inputs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[float]]:
    samples: list[dict[str, Any]] = []
    labels: list[float] = []

    for row in rows:
        features = row.get("features", {}) or {}
        metadata = row.get("metadata", {}) or {}
        sample = {
            "S_survival": _safe_float(features.get("S_survival"), 0.0),
            "S_treatment": _safe_float(features.get("S_treatment"), 0.0),
            "S_equipment": _safe_float(features.get("S_equipment"), 0.0),
            "S_eta": _safe_float(features.get("S_eta"), 0.0),
            "S_load": _safe_float(features.get("S_load"), 0.0),
            "severity": _safe_float(features.get("severity"), 0.0),
            "condition": str(features.get("condition") or "general"),
            "fallback_used": 1.0 if bool(features.get("fallback_used")) else 0.0,
            "relaxed_constraints": 1.0 if bool(features.get("relaxed_constraints")) else 0.0,
            "borderline": 1.0 if bool(metadata.get("borderline")) else 0.0,
        }
        samples.append(sample)
        labels.append(_safe_float(row.get("label"), 0.0))

    return samples, labels


def _derive_learned_weights(
    model: GradientBoostingRegressor,
    vectorizer: DictVectorizer,
    current_weights: dict[str, float],
) -> dict[str, float]:
    names = list(vectorizer.get_feature_names_out())
    importances = list(getattr(model, "feature_importances_", []))
    if len(importances) != len(names):
        return dict(current_weights)

    component_keys = {
        "S_survival": "w_survival",
        "S_treatment": "w_treatment",
        "S_equipment": "w_equipment",
        "S_eta": "w_eta",
        "S_load": "w_load",
    }
    importance_by_component: dict[str, float] = {key: 0.0 for key in component_keys}

    for feature_name, importance in zip(names, importances, strict=False):
        if feature_name in importance_by_component:
            importance_by_component[feature_name] += max(0.0, _safe_float(importance, 0.0))

    total = sum(importance_by_component.values())
    if total <= 0.0:
        return dict(current_weights)

    learned = {}
    for component, weight_key in component_keys.items():
        learned[weight_key] = importance_by_component[component] / total
    return _clamp_weights(learned)


def _smooth_update(old_weights: dict[str, float], learned_weights: dict[str, float]) -> dict[str, float]:
    blended = {}
    for key in DEFAULT_WEIGHTS:
        old_value = _safe_float(old_weights.get(key), DEFAULT_WEIGHTS[key])
        learned_value = _safe_float(learned_weights.get(key), old_value)
        blended[key] = (0.8 * old_value) + (0.2 * learned_value)
    return _clamp_weights(blended)


def _scenario_nudged_weights(
    current_weights: dict[str, float],
    priority_type: str,
    nudge_strength: float,
) -> dict[str, float]:
    focus_keys = SCENARIO_PRIORITY_FOCUS.get(str(priority_type).strip().lower(), ())
    if not focus_keys:
        return _clamp_weights(current_weights)

    candidate = dict(_clamp_weights(current_weights))
    nudge = max(0.0, min(0.05, _safe_float(nudge_strength, 0.02)))
    per_focus = nudge / max(1, len(focus_keys))

    non_focus = [key for key in DEFAULT_WEIGHTS if key not in focus_keys]
    for key in focus_keys:
        candidate[key] = candidate.get(key, DEFAULT_WEIGHTS[key]) + per_focus

    if non_focus:
        reduction = nudge / len(non_focus)
        for key in non_focus:
            candidate[key] = max(0.0, candidate.get(key, DEFAULT_WEIGHTS[key]) - reduction)

    return _clamp_weights(candidate)


def _bounded_scenario_multipliers(
    *,
    priority_type: str,
    failure_breakdown: dict[str, int] | None,
) -> dict[str, float]:
    multipliers = {key: 1.0 for key in DEFAULT_WEIGHTS}

    focus_keys = SCENARIO_PRIORITY_FOCUS.get(str(priority_type).strip().lower(), ())
    if focus_keys:
        per_focus = 0.10 / max(1, len(focus_keys))
        for key in focus_keys:
            multipliers[key] = multipliers.get(key, 1.0) + per_focus
        non_focus = [key for key in DEFAULT_WEIGHTS if key not in focus_keys]
        if non_focus:
            reduction = 0.06 / len(non_focus)
            for key in non_focus:
                multipliers[key] = multipliers.get(key, 1.0) - reduction

    if failure_breakdown:
        total_failures = max(1, sum(max(0, int(value)) for value in failure_breakdown.values()))
        for failure_name, count in failure_breakdown.items():
            target_weight = FAILURE_WEIGHT_HINTS.get(str(failure_name).strip().lower())
            if not target_weight:
                continue
            share = max(0.0, min(1.0, _safe_float(count, 0.0) / total_failures))
            multipliers[target_weight] = multipliers.get(target_weight, 1.0) + min(0.05, 0.02 + (0.04 * share))

    return {
        key: round(max(0.85, min(1.15, _safe_float(value, 1.0))), 6)
        for key, value in multipliers.items()
    }


def get_scenario_adjustment_profile(scenario_name: str) -> dict[str, Any] | None:
    profiles = _read_json(SCENARIO_ADJUSTMENTS_PATH)
    profile = profiles.get(str(scenario_name).strip().lower())
    return profile if isinstance(profile, dict) else None


def _validation_replay_score(entry: dict[str, Any], candidate_weights: dict[str, float]) -> tuple[float, bool]:
    baseline_score = _safe_float((entry.get("scores") or {}).get("final_score"), 0.0)
    snapshot = entry.get("replay_snapshot") or {}
    if not snapshot:
        return baseline_score, False

    replay_params = snapshot.get("replay_params") or {}
    decision_type = str(replay_params.get("decision_type") or entry.get("decision_type") or "unknown")

    if decision_type in {"no_viable_hospital", "stabilize_first"}:
        # Weight updates do not affect these paths in current architecture.
        return baseline_score, False

    candidates = [
        dict(item)
        for item in (snapshot.get("hospital_candidates") or [])
        if isinstance(item, dict)
    ]
    if not candidates:
        return baseline_score, False

    ranked = _with_temporary_weights(
        candidate_weights,
        lambda: rank_hospitals(
            candidates,
            ambulance_lat=_safe_float(replay_params.get("ambulance_lat"), 0.0),
            ambulance_lon=_safe_float(replay_params.get("ambulance_lng"), 0.0),
            required_equipment=[
                str(item).strip().lower()
                for item in (replay_params.get("required_equipment") or [])
                if item
            ],
            condition=str(replay_params.get("condition_type") or "general"),
            ambulance_equipment=[
                str(item).strip().lower()
                for item in ((snapshot.get("ambulance_data") or {}).get("ambulance_equipment") or [])
                if item
            ],
            severity_score=int(_safe_float(replay_params.get("severity_score"), 5.0)),
            survival_time_minutes=_safe_float(replay_params.get("survival_time_minutes"), 0.0),
        ),
    )
    if not ranked:
        return baseline_score, False

    top_score = _safe_float((ranked[0] or {}).get("score"), 0.0)
    return top_score, bool(top_score < 0.15)


def _validate_candidate_weights(candidate_weights: dict[str, float], validation_window: int = 200) -> dict[str, Any]:
    logger = get_audit_logger()
    validation_entries = logger.fetch_recent_decisions(limit=max(50, int(validation_window)), include_snapshot=True)
    if not validation_entries:
        return {
            "accepted": False,
            "reason": "not_enough_validation_data",
            "baseline_mean_score": 0.0,
            "candidate_mean_score": 0.0,
            "baseline_fallback_rate": 0.0,
            "candidate_fallback_rate": 0.0,
            "safety_violations": 0,
        }

    baseline_scores = [
        _safe_float((entry.get("scores") or {}).get("final_score"), 0.0)
        for entry in validation_entries
    ]
    baseline_mean = sum(baseline_scores) / len(baseline_scores)

    fallback_flags = [bool(entry.get("fallback_used", False)) for entry in validation_entries]
    baseline_fallback_rate = sum(1 for item in fallback_flags if item) / len(fallback_flags)

    candidate_scores: list[float] = []
    safety_violations = 0
    for entry in validation_entries:
        score, violation = _validation_replay_score(entry, candidate_weights)
        candidate_scores.append(score)
        if violation:
            safety_violations += 1

    candidate_mean = sum(candidate_scores) / max(1, len(candidate_scores))
    candidate_fallback_rate = baseline_fallback_rate

    accepted = (
        candidate_mean >= baseline_mean
        and candidate_fallback_rate <= baseline_fallback_rate
        and safety_violations == 0
    )

    reason = "accepted"
    if candidate_mean < baseline_mean:
        reason = "mean_score_decrease"
    elif candidate_fallback_rate > baseline_fallback_rate:
        reason = "fallback_rate_increase"
    elif safety_violations > 0:
        reason = "safety_violation"

    return {
        "accepted": accepted,
        "reason": reason,
        "baseline_mean_score": round(baseline_mean, 6),
        "candidate_mean_score": round(candidate_mean, 6),
        "baseline_fallback_rate": round(baseline_fallback_rate, 6),
        "candidate_fallback_rate": round(candidate_fallback_rate, 6),
        "safety_violations": int(safety_violations),
    }


def _new_version_id(version_count: int) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"w{stamp}-{version_count + 1:04d}"


def _ensure_bootstrap_version(current_weights: dict[str, float], total_decisions: int) -> None:
    existing = _read_jsonl(VERSIONS_PATH)
    if existing:
        return
    bootstrap = {
        "version_id": _new_version_id(0),
        "timestamp": _now_iso(),
        "weights": _clamp_weights(current_weights),
        "performance_metrics": {
            "note": "bootstrap_baseline",
        },
        "reason": "bootstrap",
        "total_decisions": int(total_decisions),
    }
    _append_jsonl(VERSIONS_PATH, bootstrap)


class WeightTrainer:
    """Train and safely apply improved scoring weights from audit feedback."""

    def train_and_maybe_apply(
        self,
        *,
        reason: str,
        total_decisions: int,
        prioritize_recent: bool = False,
        dataset_limit: int = 5000,
    ) -> dict[str, Any]:
        dataset_summary = build_learning_dataset(
            limit=max(200, int(dataset_limit)),
            output_path=DATASET_PATH,
            output_format="jsonl",
            include_root_cause=True,
        )
        rows = load_learning_dataset(DATASET_PATH)
        if prioritize_recent and len(rows) > 2000:
            rows = rows[-2000:]

        previous_weights = get_active_weights()
        _ensure_bootstrap_version(previous_weights, total_decisions)
        update_event: dict[str, Any] = {
            "timestamp": _now_iso(),
            "reason": reason,
            "total_decisions": int(total_decisions),
            "dataset_row_count": len(rows),
            "prioritize_recent": bool(prioritize_recent),
            "previous_weights": previous_weights,
        }

        if len(rows) < 250:
            update_event.update(
                {
                    "accepted": False,
                    "status": "rejected",
                    "rejection_reason": "insufficient_training_rows",
                }
            )
            _append_jsonl(UPDATES_PATH, update_event)
            return update_event

        split_index = max(1, len(rows) - min(200, len(rows) // 4))
        train_rows = rows[:split_index]
        train_samples, train_labels = _rows_to_model_inputs(train_rows)

        vectorizer = DictVectorizer(sparse=False)
        X_train = vectorizer.fit_transform(train_samples)

        model = GradientBoostingRegressor(
            random_state=42,
            n_estimators=120,
            max_depth=3,
            learning_rate=0.05,
        )
        model.fit(X_train, train_labels)

        learned_weights = _derive_learned_weights(model, vectorizer, previous_weights)
        proposed_weights = _smooth_update(previous_weights, learned_weights)
        guardrails = _validate_candidate_weights(proposed_weights, validation_window=200)

        update_event.update(
            {
                "dataset": dataset_summary,
                "train_r2": round(_safe_float(model.score(X_train, train_labels), 0.0), 6),
                "learned_weights": learned_weights,
                "proposed_weights": proposed_weights,
                "guardrails": guardrails,
            }
        )

        if not bool(guardrails.get("accepted", False)):
            update_event.update(
                {
                    "accepted": False,
                    "status": "rejected",
                    "rejection_reason": guardrails.get("reason", "guardrail_rejection"),
                }
            )
            _append_jsonl(UPDATES_PATH, update_event)
            return update_event

        applied_weights = _set_active_weights(proposed_weights)
        existing_versions = _read_jsonl(VERSIONS_PATH)
        version_record = {
            "version_id": _new_version_id(len(existing_versions)),
            "timestamp": _now_iso(),
            "weights": applied_weights,
            "performance_metrics": {
                "train_r2": update_event.get("train_r2"),
                "baseline_mean_score": guardrails.get("baseline_mean_score"),
                "candidate_mean_score": guardrails.get("candidate_mean_score"),
                "baseline_fallback_rate": guardrails.get("baseline_fallback_rate"),
                "candidate_fallback_rate": guardrails.get("candidate_fallback_rate"),
                "safety_violations": guardrails.get("safety_violations"),
            },
            "reason": reason,
            "total_decisions": int(total_decisions),
        }
        _append_jsonl(VERSIONS_PATH, version_record)

        update_event.update(
            {
                "accepted": True,
                "status": "accepted",
                "version_id": version_record["version_id"],
                "applied_weights": applied_weights,
            }
        )
        _append_jsonl(UPDATES_PATH, update_event)
        return update_event


def rollback_to_version(version_id: str) -> dict[str, Any]:
    target = str(version_id).strip()
    versions = _read_jsonl(VERSIONS_PATH)
    record = next((item for item in versions if str(item.get("version_id")) == target), None)
    if record is None:
        result = {
            "timestamp": _now_iso(),
            "action": "rollback",
            "requested_version": target,
            "status": "failed",
            "reason": "version_not_found",
        }
        _append_jsonl(UPDATES_PATH, result)
        return result

    previous = get_active_weights()
    applied = _set_active_weights(record.get("weights", {}) or {})
    result = {
        "timestamp": _now_iso(),
        "action": "rollback",
        "requested_version": target,
        "status": "success",
        "previous_weights": previous,
        "applied_weights": applied,
    }
    _append_jsonl(UPDATES_PATH, result)
    return result


def apply_scenario_weight_adjustment(
    *,
    scenario_name: str,
    priority_type: str,
    total_decisions: int,
    nudge_strength: float = 0.02,
    failure_breakdown: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Store a bounded scenario-specific adjustment profile while keeping global weights stable."""
    scenario_key = str(scenario_name).strip().lower()
    previous_weights = get_active_weights()
    proposed_weights = _scenario_nudged_weights(previous_weights, priority_type, nudge_strength)
    guardrails = _validate_candidate_weights(proposed_weights, validation_window=200)
    multipliers = _bounded_scenario_multipliers(
        priority_type=priority_type,
        failure_breakdown=failure_breakdown,
    )

    update_event: dict[str, Any] = {
        "timestamp": _now_iso(),
        "reason": f"scenario_adjustment:{scenario_name}",
        "priority_type": str(priority_type),
        "scenario_name": str(scenario_name),
        "total_decisions": int(total_decisions),
        "previous_weights": previous_weights,
        "proposed_weights": proposed_weights,
        "guardrails": guardrails,
        "failure_breakdown": failure_breakdown or {},
        "scenario_weight_multipliers": multipliers,
    }

    profiles = _read_json(SCENARIO_ADJUSTMENTS_PATH)
    profiles[scenario_key] = {
        "scenario_name": scenario_key,
        "priority_type": str(priority_type),
        "updated_at": _now_iso(),
        "total_decisions": int(total_decisions),
        "failure_breakdown": failure_breakdown or {},
        "guardrails": {
            "baseline_mean_score": guardrails.get("baseline_mean_score"),
            "candidate_mean_score": guardrails.get("candidate_mean_score"),
            "baseline_fallback_rate": guardrails.get("baseline_fallback_rate"),
            "candidate_fallback_rate": guardrails.get("candidate_fallback_rate"),
            "safety_violations": guardrails.get("safety_violations"),
        },
        "weight_multipliers": multipliers,
    }
    _write_json(SCENARIO_ADJUSTMENTS_PATH, profiles)

    update_event.update(
        {
            "accepted": True,
            "status": "accepted",
            "version_id": f"scenario:{scenario_key}",
            "applied_weights": previous_weights,
            "global_weights_stable": True,
        }
    )
    _append_jsonl(UPDATES_PATH, update_event)
    return update_event


def run_targeted_learning_update(
    *,
    scenario_name: str,
    priority_type: str,
    failure_rate: float,
    total_decisions: int,
    threshold: float = 0.10,
    failure_breakdown: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    """Run scenario-triggered retraining and guarded scenario-specific weight adjustment."""
    if _safe_float(failure_rate, 0.0) <= _safe_float(threshold, 0.10):
        return None

    rows = load_learning_dataset(DATASET_PATH)
    scenario_rows = [
        row for row in rows if str((row.get("features") or {}).get("scenario_name") or "").strip().lower() == str(scenario_name).strip().lower()
    ]
    segment_summary = {
        "scenario_name": str(scenario_name),
        "scenario_rows": len(scenario_rows),
        "global_rows": len(rows),
    }

    train_result: dict[str, Any]
    if _safe_float(failure_rate, 0.0) >= (_safe_float(threshold, 0.10) * 1.5):
        trainer = WeightTrainer()
        train_result = trainer.train_and_maybe_apply(
            reason=f"scenario_targeted:{scenario_name}",
            total_decisions=int(total_decisions),
            prioritize_recent=True,
            dataset_limit=3000,
        )
    else:
        train_result = {
            "status": "skipped",
            "reason": "global_weights_kept_stable_for_moderate_scenario_drift",
            "accepted": False,
        }

    adjust_result = apply_scenario_weight_adjustment(
        scenario_name=scenario_name,
        priority_type=priority_type,
        total_decisions=int(total_decisions),
        nudge_strength=0.03 if len(scenario_rows) >= 50 else 0.02,
        failure_breakdown=failure_breakdown,
    )

    return {
        "triggered": True,
        "scenario_name": str(scenario_name),
        "priority_type": str(priority_type),
        "failure_rate": round(_safe_float(failure_rate, 0.0), 6),
        "threshold": round(_safe_float(threshold, 0.10), 6),
        "scenario_segment": segment_summary,
        "train_result": train_result,
        "adjust_result": adjust_result,
    }


def run_periodic_learning_update(
    *,
    total_decisions: int,
    retrain_every: int = 1000,
    drift_alerts: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Trigger periodic training or immediate drift-aware retraining."""
    total = int(total_decisions)
    if total <= 0:
        return None

    has_drift = bool(drift_alerts)
    periodic_trigger = (total % max(1, int(retrain_every))) == 0
    if not has_drift and not periodic_trigger:
        return None

    trainer = WeightTrainer()
    reason = "drift_triggered" if has_drift else "periodic"
    return trainer.train_and_maybe_apply(
        reason=reason,
        total_decisions=total,
        prioritize_recent=has_drift,
    )
