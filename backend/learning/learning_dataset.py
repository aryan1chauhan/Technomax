"""Build structured learning datasets from decision audit logs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from audit.audit_logger import get_audit_logger
from audit.replay_engine import DecisionReplayEngine

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
DEFAULT_DATASET_PATH = ARTIFACT_DIR / "learning_dataset.jsonl"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _decision_quality_score(decision: dict[str, Any], root_cause: str | None) -> float:
    scores = decision.get("scores", {}) or {}
    final_score = _safe_float(scores.get("final_score"), 0.0)

    penalty = 0.0
    if bool(decision.get("fallback_used", False)):
        penalty += 0.12
    if bool(decision.get("relaxed_constraints", False)):
        penalty += 0.05
    if bool(decision.get("borderline", False)):
        penalty += 0.08
    if str(decision.get("failure_type", "none")) != "none":
        penalty += 0.10
    if root_cause:
        penalty += 0.05

    return round(_clamp(final_score - penalty), 6)


def _extract_root_cause(
    replay_engine: DecisionReplayEngine | None,
    decision: dict[str, Any],
    include_root_cause: bool,
) -> str | None:
    if not include_root_cause or replay_engine is None:
        return None

    case_id = str(decision.get("case_id") or "")
    decision_id = int(decision.get("id") or 0)
    if not case_id or decision_id <= 0:
        return None

    try:
        replay = replay_engine.replay_decision(case_id=case_id, decision_id=decision_id)
    except (RuntimeError, ValueError, TypeError, KeyError):
        return None

    root = replay.get("root_cause") or {}
    if not isinstance(root, dict):
        return None
    value = root.get("root_cause")
    return str(value) if value else None


def _to_dataset_row(
    decision: dict[str, Any],
    root_cause: str | None,
) -> dict[str, Any]:
    scores = decision.get("scores", {}) or {}
    replay_snapshot = decision.get("replay_snapshot") or {}
    case_input = replay_snapshot.get("case_input") or {}
    replay_params = replay_snapshot.get("replay_params") or {}
    scenario_context = replay_params.get("scenario_context") or {}
    scenario_name = (
        case_input.get("scenario_name")
        or scenario_context.get("scenario_name")
        or "default"
    )
    priority_type = (
        case_input.get("scenario_priority_type")
        or scenario_context.get("priority_type")
        or "default"
    )

    features = {
        "S_survival": _safe_float(scores.get("S_survival"), 0.0),
        "S_treatment": _safe_float(scores.get("S_treatment"), 0.0),
        "S_equipment": _safe_float(scores.get("S_equipment"), 0.0),
        "S_eta": _safe_float(scores.get("S_eta"), 0.0),
        "S_load": _safe_float(scores.get("S_load"), 0.0),
        "condition": str(decision.get("condition") or "general"),
        "severity": _safe_float(decision.get("severity"), 0.0),
        "fallback_used": bool(decision.get("fallback_used", False)),
        "relaxed_constraints": bool(decision.get("relaxed_constraints", False)),
        "scenario_name": str(scenario_name),
        "priority_type": str(priority_type),
    }

    metadata = {
        "failure_type": str(decision.get("failure_type") or "none"),
        "borderline": bool(decision.get("borderline", False)),
        "root_cause": root_cause,
        "expected_behavior": case_input.get("expected_behavior"),
        "behavior_corrections": (replay_snapshot.get("flags") or {}).get("behavior_corrections", []),
    }

    label = _decision_quality_score(decision, root_cause)
    return {
        "decision_id": int(decision.get("id") or 0),
        "case_id": str(decision.get("case_id") or "unknown"),
        "timestamp": str(decision.get("timestamp") or ""),
        "features": features,
        "label": label,
        "metadata": metadata,
    }


def _write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "decision_id",
        "case_id",
        "timestamp",
        "label",
        "S_survival",
        "S_treatment",
        "S_equipment",
        "S_eta",
        "S_load",
        "condition",
        "severity",
        "scenario_name",
        "priority_type",
        "fallback_used",
        "relaxed_constraints",
        "failure_type",
        "borderline",
        "root_cause",
    ]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            features = row.get("features", {}) or {}
            metadata = row.get("metadata", {}) or {}
            writer.writerow(
                {
                    "decision_id": row.get("decision_id"),
                    "case_id": row.get("case_id"),
                    "timestamp": row.get("timestamp"),
                    "label": row.get("label"),
                    "S_survival": features.get("S_survival"),
                    "S_treatment": features.get("S_treatment"),
                    "S_equipment": features.get("S_equipment"),
                    "S_eta": features.get("S_eta"),
                    "S_load": features.get("S_load"),
                    "condition": features.get("condition"),
                    "severity": features.get("severity"),
                    "scenario_name": features.get("scenario_name"),
                    "priority_type": features.get("priority_type"),
                    "fallback_used": features.get("fallback_used"),
                    "relaxed_constraints": features.get("relaxed_constraints"),
                    "failure_type": metadata.get("failure_type"),
                    "borderline": metadata.get("borderline"),
                    "root_cause": metadata.get("root_cause"),
                }
            )


def build_learning_dataset(
    *,
    limit: int = 5000,
    output_path: Path | None = None,
    output_format: str = "jsonl",
    include_root_cause: bool = True,
) -> dict[str, Any]:
    """Build learning dataset from recent audit entries and write to disk."""
    audit_logger = get_audit_logger()
    decisions = audit_logger.fetch_recent_decisions(limit=max(10, int(limit)), include_snapshot=True)

    replay_engine: DecisionReplayEngine | None = None
    if include_root_cause:
        try:
            replay_engine = DecisionReplayEngine()
        except (RuntimeError, ValueError, TypeError, KeyError):
            replay_engine = None

    rows: list[dict[str, Any]] = []
    for decision in decisions:
        root_cause = _extract_root_cause(replay_engine, decision, include_root_cause)
        rows.append(_to_dataset_row(decision, root_cause))

    target_path = output_path or DEFAULT_DATASET_PATH
    fmt = output_format.strip().lower()
    if fmt == "auto":
        fmt = target_path.suffix.replace(".", "").lower() or "jsonl"

    if fmt == "csv":
        _write_csv(rows, target_path)
    else:
        _write_jsonl(rows, target_path)

    fallback_rate = 0.0
    if rows:
        fallback_count = sum(1 for row in rows if bool((row.get("features") or {}).get("fallback_used")))
        fallback_rate = fallback_count / len(rows)

    return {
        "dataset_path": str(target_path),
        "format": fmt,
        "row_count": len(rows),
        "fallback_rate": round(fallback_rate, 6),
    }


def load_learning_dataset(dataset_path: Path | None = None) -> list[dict[str, Any]]:
    """Load learning dataset rows from JSONL or CSV."""
    path = dataset_path or DEFAULT_DATASET_PATH
    if not path.exists():
        return []

    fmt = path.suffix.replace(".", "").lower()
    if fmt == "csv":
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for record in reader:
                features = {
                    "S_survival": _safe_float(record.get("S_survival"), 0.0),
                    "S_treatment": _safe_float(record.get("S_treatment"), 0.0),
                    "S_equipment": _safe_float(record.get("S_equipment"), 0.0),
                    "S_eta": _safe_float(record.get("S_eta"), 0.0),
                    "S_load": _safe_float(record.get("S_load"), 0.0),
                    "condition": str(record.get("condition") or "general"),
                    "severity": _safe_float(record.get("severity"), 0.0),
                    "scenario_name": str(record.get("scenario_name") or "default"),
                    "priority_type": str(record.get("priority_type") or "default"),
                    "fallback_used": str(record.get("fallback_used", "False")).lower() == "true",
                    "relaxed_constraints": str(record.get("relaxed_constraints", "False")).lower() == "true",
                }
                metadata = {
                    "failure_type": str(record.get("failure_type") or "none"),
                    "borderline": str(record.get("borderline", "False")).lower() == "true",
                    "root_cause": str(record.get("root_cause") or "") or None,
                }
                rows.append(
                    {
                        "decision_id": int(record.get("decision_id") or 0),
                        "case_id": str(record.get("case_id") or "unknown"),
                        "timestamp": str(record.get("timestamp") or ""),
                        "features": features,
                        "label": _safe_float(record.get("label"), 0.0),
                        "metadata": metadata,
                    }
                )
        return rows

    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
    return rows
