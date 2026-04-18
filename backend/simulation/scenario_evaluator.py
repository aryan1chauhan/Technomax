"""Scenario simulation evaluator with behavior checks and failure intelligence."""

from __future__ import annotations

import statistics
from collections import Counter
from typing import Any

from app.engine.dispatch_engine import run_dispatch
from audit.audit_logger import get_audit_logger
from learning.weight_trainer import get_scenario_adjustment_profile, run_targeted_learning_update

from simulation.scenario_generator import ScenarioGenerator, SimulationCase
from simulation.scenario_library import list_scenarios


ROOT_CAUSE_BY_FAILURE: dict[str, str] = {
    "behavior_mismatch": "Decision policy drift against expected scenario behavior.",
    "fallback_dependency": "Constraint pressure forcing fallback paths.",
    "no_destination": "Capacity and acceptance constraints eliminated all options.",
    "equipment_gap": "Required equipment mapping underweighted or unavailable.",
    "score_collapse": "Scoring confidence deteriorated under scenario stress.",
    "safety_violation": "Safety invariants were violated in dispatch output.",
    "dispatch_crash": "Dispatch execution raised an exception.",
    "none": "No dominant failure mode detected.",
}

FAILURE_TO_COMPONENT: dict[str, str] = {
    "eta_delay": "S_eta",
    "late_handover": "S_eta",
    "specialty_mismatch": "S_treatment",
    "treatment_mismatch": "S_treatment",
    "stabilization_miss": "S_survival",
    "stabilization_skip": "S_survival",
    "equipment_gap": "S_equipment",
    "bed_shortage": "S_load",
    "fallback_dependency": "S_load",
}

_SAFETY_SCORE_FLOOR = 0.15


class ScenarioEvaluator:
    def __init__(self, *, seed: int = 42, failure_threshold: float = 0.10) -> None:
        self.generator = ScenarioGenerator(seed=seed)
        self.seed = int(seed)
        self.failure_threshold = float(failure_threshold)

    async def evaluate_scenario(self, scenario_name: str, cases: int = 100) -> dict[str, Any]:
        generated = self.generator.generate_cases(scenario_name, cases)
        if not generated:
            return {
                "scenario": scenario_name,
                "total_cases": 0,
                "metrics": {
                    "scenario_mean_score": 0.0,
                    "scenario_failure_rate": 0.0,
                    "fallback_rate": 0.0,
                    "correct_behavior_rate": 0.0,
                },
                "dominant_failure_mode": "none",
                "dominant_root_cause": ROOT_CAUSE_BY_FAILURE["none"],
                "failure_breakdown": {},
                "mismatch_alerts": [],
                "worst_cases": [],
                "targeted_learning_update": None,
                "safety_violations": 0,
                "crashes": 0,
            }

        profile = get_scenario_adjustment_profile(scenario_name) or {}
        profile_failure_components = _derive_profile_failure_components(profile)
        scenario_results: list[dict[str, Any]] = []
        for case in generated:
            scenario_results.append(
                await self._evaluate_case(
                    case,
                    profile_failure_components=profile_failure_components,
                )
            )

        scores = [float(item["score"]) for item in scenario_results]
        raw_scores = [float(item["raw_score"]) for item in scenario_results]
        fallback_count = sum(1 for item in scenario_results if item["fallback_used"])
        behavior_correct_count = sum(1 for item in scenario_results if item["behavior_match"])
        crash_count = sum(1 for item in scenario_results if bool(item.get("crash", False)))
        safety_violation_count = sum(len(item.get("safety_violations", [])) for item in scenario_results)
        failures = [item for item in scenario_results if item["failure_type"] != "none"]
        mismatches = [item for item in scenario_results if not item["behavior_match"]]
        mismatch_penalty_delta = sum(float(item["mismatch_penalty_delta"]) for item in mismatches)

        failure_counter = Counter(item["failure_type"] for item in scenario_results)
        dominant_failure = "none"
        if failures:
            dominant_failure = Counter(item["failure_type"] for item in failures).most_common(1)[0][0]

        failure_rate = len(failures) / max(1, len(scenario_results))
        failure_reweighting = _derive_failure_mode_reweighting(
            scenario_name=generated[0].scenario_name,
            failure_counter=failure_counter,
        )

        learning_update = run_targeted_learning_update(
            scenario_name=generated[0].scenario_name,
            priority_type=generated[0].priority_type,
            failure_rate=failure_rate,
            total_decisions=_get_total_decisions(),
            threshold=self.failure_threshold,
            failure_breakdown=failure_reweighting["failure_breakdown"],
        )
        scenario_adjustment_profile = get_scenario_adjustment_profile(generated[0].scenario_name)

        mismatch_alerts = [
            {
                "case_id": item["case_id"],
                "alert": item["behavior_reason"],
                "decision_type": item["decision_type"],
                "selected_hospital": item["selected_hospital"],
            }
            for item in scenario_results
            if not item["behavior_match"]
        ]

        worst_cases = sorted(
            scenario_results,
            key=lambda item: (1 if item["behavior_match"] else 0, float(item["score"])),
        )[:5]

        return {
            "scenario": generated[0].scenario_name,
            "priority_type": generated[0].priority_type,
            "expected_behavior": generated[0].expected_behavior,
            "total_cases": len(scenario_results),
            "metrics": {
                "scenario_mean_score": round(statistics.fmean(scores) if scores else 0.0, 6),
                "scenario_mean_raw_score": round(statistics.fmean(raw_scores) if raw_scores else 0.0, 6),
                "scenario_failure_rate": round(failure_rate, 6),
                "fallback_rate": round(fallback_count / len(scenario_results), 6),
                "correct_behavior_rate": round(behavior_correct_count / len(scenario_results), 6),
                "behavior_mismatch_rate": round(len(mismatches) / len(scenario_results), 6),
                "mismatch_penalty_impact": round(mismatch_penalty_delta / len(scenario_results), 6),
                "scenario_safety_violations": int(safety_violation_count),
                "scenario_crashes": int(crash_count),
            },
            "dominant_failure_mode": dominant_failure,
            "dominant_root_cause": ROOT_CAUSE_BY_FAILURE.get(dominant_failure, "Unknown"),
            "failure_breakdown": dict(failure_counter),
            "failure_mode_reweighting": failure_reweighting,
            "mismatch_alerts": mismatch_alerts,
            "worst_cases": [
                {
                    "case_id": item["case_id"],
                    "score": round(float(item["score"]), 6),
                    "decision_type": item["decision_type"],
                    "failure_type": item["failure_type"],
                    "root_cause": item["root_cause"],
                    "selected_hospital": item["selected_hospital"],
                    "behavior_reason": item["behavior_reason"],
                }
                for item in worst_cases
            ],
            "targeted_learning_update": learning_update,
            "scenario_adjustment_profile": scenario_adjustment_profile,
            "profile_failure_components": profile_failure_components,
            "safety_violations": int(safety_violation_count),
            "crashes": int(crash_count),
        }

    async def evaluate_all(self, *, cases_per_scenario: int = 100, scenario_names: list[str] | None = None) -> dict[str, Any]:
        selected = scenario_names if scenario_names else list_scenarios()
        reports: dict[str, dict[str, Any]] = {}

        for scenario_name in selected:
            reports[scenario_name] = await self.evaluate_scenario(scenario_name, cases=cases_per_scenario)

        all_scores = [report["metrics"]["scenario_mean_score"] for report in reports.values() if report.get("total_cases")]
        all_failures = [report["metrics"]["scenario_failure_rate"] for report in reports.values() if report.get("total_cases")]
        all_mismatch = [report["metrics"].get("behavior_mismatch_rate", 0.0) for report in reports.values() if report.get("total_cases")]
        total_safety_violations = sum(int(report.get("safety_violations", 0)) for report in reports.values())
        total_crashes = sum(int(report.get("crashes", 0)) for report in reports.values())
        min_scores = [
            min((float(case.get("score", 0.0)) for case in report.get("worst_cases", [])), default=0.0)
            for report in reports.values()
            if report.get("total_cases")
        ]

        return {
            "seed": self.seed,
            "failure_threshold": round(self.failure_threshold, 6),
            "cases_per_scenario": int(cases_per_scenario),
            "overall": {
                "mean_scenario_score": round(statistics.fmean(all_scores) if all_scores else 0.0, 6),
                "mean_failure_rate": round(statistics.fmean(all_failures) if all_failures else 0.0, 6),
                "mean_behavior_mismatch_rate": round(statistics.fmean(all_mismatch) if all_mismatch else 0.0, 6),
                "min_observed_score": round(min(min_scores) if min_scores else 0.0, 6),
                "scenario_count": len(reports),
                "total_safety_violations": int(total_safety_violations),
                "total_crashes": int(total_crashes),
            },
            "scenarios": reports,
        }

    async def _evaluate_case(
        self,
        case: SimulationCase,
        profile_failure_components: list[str] | None = None,
    ) -> dict[str, Any]:
        kwargs = case.to_dispatch_kwargs()
        scenario_context = dict(kwargs.get("scenario_context") or {})
        if profile_failure_components:
            scenario_context["failure_components"] = profile_failure_components[:1]
        kwargs["scenario_context"] = scenario_context

        try:
            result = await run_dispatch(**kwargs)
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as exc:
            return {
                "case_id": case.case_id,
                "raw_score": 0.0,
                "score": 0.0,
                "mismatch_penalty_applied": False,
                "mismatch_penalty_delta": 0.0,
                "fallback_used": True,
                "behavior_match": False,
                "behavior_reason": f"Dispatch crashed: {type(exc).__name__}",
                "failure_type": "dispatch_crash",
                "root_cause": ROOT_CAUSE_BY_FAILURE["dispatch_crash"],
                "decision_type": "dispatch_crash",
                "selected_hospital": "none",
                "safety_violations": ["dispatch_crash"],
                "crash": True,
            }

        raw_score = _extract_score(result)
        fallback_used = _extract_fallback(result)

        behavior_match, behavior_reason = _validate_behavior(case, result)
        mismatch_penalty = 0.70 if not behavior_match else 1.0
        score = max(0.0, min(1.0, float(raw_score) * mismatch_penalty))
        safety_violations = _validate_safety(result, score)
        failure_type = _classify_failure(case, result, score, fallback_used, behavior_match)
        if safety_violations and failure_type == "none":
            failure_type = "safety_violation"
        root_cause = ROOT_CAUSE_BY_FAILURE.get(failure_type, "Unknown")

        primary = result.get("primary_destination") or {}
        selected = str(primary.get("hospital_name", "none"))
        decision_type = str(result.get("decision_type", "unknown"))

        return {
            "case_id": case.case_id,
            "raw_score": raw_score,
            "score": score,
            "mismatch_penalty_applied": not behavior_match,
            "mismatch_penalty_delta": max(0.0, float(raw_score) - float(score)),
            "fallback_used": fallback_used,
            "behavior_match": behavior_match,
            "behavior_reason": behavior_reason,
            "failure_type": failure_type,
            "root_cause": root_cause,
            "decision_type": decision_type,
            "selected_hospital": selected,
            "safety_violations": safety_violations,
            "crash": False,
        }


def _derive_profile_failure_components(profile: dict[str, Any] | None) -> list[str]:
    if not isinstance(profile, dict):
        return []
    breakdown = profile.get("failure_breakdown")
    if not isinstance(breakdown, dict):
        return []

    filtered = {
        str(name).strip().lower(): int(value)
        for name, value in breakdown.items()
        if str(name).strip().lower() != "none" and int(value) > 0
    }
    if not filtered:
        return []
    dominant = max(filtered.items(), key=lambda item: item[1])[0]
    return [dominant]


def _validate_safety(result: dict[str, Any], score: float) -> list[str]:
    violations: list[str] = []
    decision_type = str(result.get("decision_type", "")).strip().lower()
    if not decision_type:
        violations.append("empty_decision_type")

    primary = result.get("primary_destination") or {}
    if decision_type != "no_viable_hospital":
        if not primary or not str(primary.get("hospital_name", "")).strip():
            violations.append("missing_primary_destination")

    if decision_type != "no_viable_hospital" and float(score) < _SAFETY_SCORE_FLOOR:
        violations.append("score_below_safety_floor")

    return violations


def _derive_failure_mode_reweighting(
    *,
    scenario_name: str,
    failure_counter: Counter[str],
) -> dict[str, Any]:
    filtered = {
        key: int(value)
        for key, value in failure_counter.items()
        if str(key) != "none" and int(value) > 0
    }
    if not filtered:
        return {
            "scenario_name": scenario_name,
            "failure_breakdown": {},
            "component_shifts": {},
            "dominant_failure": "none",
        }

    dominant_failure = max(filtered.items(), key=lambda item: item[1])[0]
    component = FAILURE_TO_COMPONENT.get(dominant_failure)
    component_shifts: dict[str, float] = {}
    if component:
        component_shifts[component] = 0.05

    return {
        "scenario_name": scenario_name,
        "failure_breakdown": filtered,
        "component_shifts": component_shifts,
        "dominant_failure": dominant_failure,
    }


def _extract_score(result: dict[str, Any]) -> float:
    ranked = result.get("ranked_candidates") or []
    if ranked:
        try:
            return max(0.0, min(1.0, float(ranked[0].get("score", 0.0))))
        except (TypeError, ValueError):
            pass

    reasoning = result.get("reasoning") or {}
    try:
        return max(0.0, min(1.0, float(reasoning.get("ml_score", 0.0))))
    except (TypeError, ValueError):
        return 0.0


def _extract_fallback(result: dict[str, Any]) -> bool:
    reasoning = result.get("reasoning") or {}
    decision_type = str(result.get("decision_type", "")).strip().lower()
    return bool(reasoning.get("fallback_triggers")) or decision_type == "no_viable_hospital"


def _selected_hospital(case: SimulationCase, result: dict[str, Any]) -> dict[str, Any] | None:
    primary = result.get("primary_destination") or {}
    selected_name = str(primary.get("hospital_name", "")).strip().lower()
    if not selected_name:
        return None
    for hospital in case.hospitals:
        if str(hospital.get("name", "")).strip().lower() == selected_name:
            return hospital
    return None


def _validate_behavior(case: SimulationCase, result: dict[str, Any]) -> tuple[bool, str]:
    decision_type = str(result.get("decision_type", "")).strip().lower()
    if decision_type == "no_viable_hospital":
        return False, "No viable destination produced under expected scenario constraints."

    selected = _selected_hospital(case, result)
    if not selected:
        return False, "Primary destination was missing from scenario hospital pool."

    tags = {str(item).strip().lower() for item in selected.get("scenario_tags", [])}
    equipment = {str(item).strip().lower() for item in selected.get("equipment", [])}
    reasoning = result.get("reasoning") or {}
    stabilization_required = bool(reasoning.get("stabilization_required", False))
    eta_minutes = float((result.get("primary_destination") or {}).get("eta_minutes", 9999.0) or 9999.0)

    if case.scenario_name == "cardiac_emergency":
        if stabilization_required and decision_type != "stabilize_first" and eta_minutes > 12.0:
            return False, "Unstable cardiac case skipped stabilization for a delayed transfer."
        if "cardiac" not in tags and "defibrillator" not in equipment:
            return False, "Cardiac emergency routed to non-cardiac destination."
        return True, "Cardiac time-critical behavior satisfied."

    if case.scenario_name == "stroke_specialty":
        if not ({"stroke", "neuro"} & tags or {"ct_scan", "stroke_unit", "neurology"} & equipment):
            return False, "Stroke case missed specialty-capable destination."
        return True, "Stroke specialty routing satisfied."

    if case.scenario_name == "trauma_stabilization":
        if stabilization_required and decision_type != "stabilize_first" and eta_minutes > 15.0:
            return False, "Severe trauma case should stabilize before long transfer."
        if "trauma" not in tags and not ({"trauma_center", "surgery", "blood_bank", "lab"} & equipment):
            return False, "Trauma case missed trauma-capable destination."
        return True, "Trauma stabilization behavior satisfied."

    if case.scenario_name == "respiratory_failure":
        required = {str(item).strip().lower() for item in case.required_equipment}
        if not required.issubset(equipment):
            return False, "Respiratory case selected destination without required equipment match."
        return True, "Respiratory equipment routing satisfied."

    if case.scenario_name == "mixed_chaos":
        if bool(reasoning.get("input_corruption_detected", False)) and not bool(reasoning.get("relaxed_constraints_mode", False)):
            return False, "Mixed-chaos case detected corruption without relaxation safeguards."
        return True, "Mixed-chaos safeguards satisfied."

    return True, "No explicit behavior rule applied."


def _classify_failure(
    case: SimulationCase,
    result: dict[str, Any],
    score: float,
    fallback_used: bool,
    behavior_match: bool,
) -> str:
    decision_type = str(result.get("decision_type", "")).strip().lower()
    if decision_type == "no_viable_hospital":
        return "no_destination"
    if not behavior_match:
        return "behavior_mismatch"

    selected = _selected_hospital(case, result)
    if selected:
        equipment = {str(item).strip().lower() for item in selected.get("equipment", [])}
        required = {str(item).strip().lower() for item in case.required_equipment}
        if required and not required.issubset(equipment):
            return "equipment_gap"

    if fallback_used:
        return "fallback_dependency"
    if float(score) < 0.35:
        return "score_collapse"
    return "none"


def _get_total_decisions() -> int:
    logger = get_audit_logger()
    recent = logger.fetch_recent_decisions(limit=1)
    if recent:
        try:
            return max(1, int(recent[-1].get("id", 1)))
        except (TypeError, ValueError):
            pass

    try:
        return max(1, int(getattr(logger, "_decision_count", 1)))
    except (TypeError, ValueError):
        return 1
