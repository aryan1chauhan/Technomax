"""Full trust pipeline: chaos dataset, quality scoring, oscillation, optimizer, alerts."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import random
import statistics
from typing import Any

import numpy as np

from tests.chaos_dataset import ChaosCase, generate_dataset
from tests.adversarial_dataset import AdversarialCase, generate_adversarial_dataset
from tests.trust_layer import ACTIVE_WEIGHTS, case_to_dispatch_kwargs
from tests.validation_harness import SyntheticCaseGenerator, CaseInput
from tests.failure_classification import FAILURE_CATEGORIES, classify_failure


def _as_case_input(chaos_case: ChaosCase) -> CaseInput:
    """Map ChaosCase to CaseInput for dispatch harness."""
    # Minimal hospital pool, using existing synthetic generator to keep schema consistent.
    hospitals = SyntheticCaseGenerator.generate_critical_unstable_cases()[0].hospitals

    return CaseInput(
        case_id=chaos_case.case_id,
        ambulance_equipment=["oxygen"],
        condition=chaos_case.condition,
        severity_score=chaos_case.severity,
        patient_vitals=chaos_case.vitals,
        required_equipment=chaos_case.required_equipment,
        hospitals=hospitals,
    )


def _infer_priority_type(scenario_name: str) -> str:
    name = str(scenario_name or "").strip().lower()
    if "contradictory" in name or "conflict" in name:
        return "conflict_resolution"
    if "gps" in name or "corrupt" in name:
        return "robustness"
    if "no_match" in name or "overload" in name:
        return "fallback_handling"
    if "missing" in name:
        return "stabilization"
    return "default"


def _infer_expected_behavior(scenario_name: str) -> str:
    name = str(scenario_name or "").strip().lower()
    if "contradictory" in name:
        return "resolve conflicting severity and vitals deterministically"
    if "gps" in name:
        return "degrade gracefully under eta uncertainty"
    if "corrupt" in name:
        return "prefer robust treatment over noisy inputs"
    if "no_match" in name or "overload" in name:
        return "safe fallback with transparent constraints"
    if "missing" in name:
        return "remain safe under sparse vitals"
    return "maintain stable dispatch quality"


def _infer_conflicting_signals(scenario_name: str) -> bool:
    name = str(scenario_name or "").strip().lower()
    return "contradictory" in name or "conflict" in name or "chaos" in name


def _infer_uncertainty(scenario_name: str) -> float:
    name = str(scenario_name or "").strip().lower()
    if "contradictory" in name:
        return 0.9
    if "corrupt" in name or "gps" in name:
        return 0.8
    if "missing" in name:
        return 0.7
    if "no_match" in name or "overload" in name:
        return 0.6
    return 0.2


def _is_fallback_decision(result: dict[str, Any]) -> bool:
    decision_type = str(result.get("decision_type", "")).strip().lower()
    reasoning = result.get("reasoning", {}) or {}

    if decision_type == "no_viable_hospital":
        return True

    if reasoning.get("fallback_triggers"):
        return True

    # Direct decisions with no ML score indicate ETA fallback ranking path.
    if decision_type == "direct" and reasoning.get("ml_score") is None and not reasoning.get("best_effort_ranking_used"):
        return True

    return False


def _fallback_breakdown_template() -> dict[str, int]:
    return {
        "missing_equipment": 0,
        "no_viable": 0,
        "eta_limit": 0,
        "survival_limit": 0,
        "input_corruption": 0,
    }


def _extract_fallback_breakdown_keys(result: dict[str, Any]) -> list[str]:
    reasoning = result.get("reasoning", {}) or {}
    triggers = {str(item) for item in (reasoning.get("fallback_triggers") or [])}
    keys: list[str] = []

    if "missing_critical_equipment" in triggers:
        keys.append("missing_equipment")
    if "no_viable_hospital_after_constraints" in triggers:
        keys.append("no_viable")
    if "eta_too_high" in triggers:
        keys.append("eta_limit")
    if "survival_below_threshold" in triggers:
        keys.append("survival_limit")
    if "corrupted_input_detected" in triggers or reasoning.get("input_corruption_detected"):
        keys.append("input_corruption")

    if not keys and str(result.get("decision_type", "")).strip().lower() == "no_viable_hospital":
        keys.append("no_viable")

    return list(dict.fromkeys(keys))


def _validate_adversarial_safety(
    *,
    case: AdversarialCase,
    result: dict[str, Any],
    score: float,
    failure_type: str,
) -> list[str]:
    violations: list[str] = []

    decision_type = str(result.get("decision_type", "")).strip()
    primary = result.get("primary_destination")
    reasoning = result.get("reasoning", {}) or {}

    if not decision_type:
        violations.append("missing_decision_type")

    if decision_type != "no_viable_hospital" and not primary:
        violations.append("empty_primary_destination")

    if score < 0.15:
        violations.append("score_floor_breach")

    if failure_type not in FAILURE_CATEGORIES:
        violations.append("invalid_failure_category")

    if case.scenario == "missing_all_vitals":
        if reasoning.get("stability_score") is None or reasoning.get("estimated_survival_time") is None:
            violations.append("missing_reasoning_under_sparse_vitals")

    if case.scenario == "contradictory_low_severity_critical_oxygen":
        oxygen = (case.case_input.patient_vitals or {}).get("oxygen")
        eta = float((primary or {}).get("eta_minutes", reasoning.get("eta_minutes", 9999.0)))
        stabilization_required = bool(reasoning.get("stabilization_required"))
        try:
            oxygen_value = float(oxygen)
        except (TypeError, ValueError):
            oxygen_value = None

        if oxygen_value is not None and oxygen_value < 85.0 and (not stabilization_required and eta > 20.0):
            violations.append("critical_oxygen_not_prioritized")

    if case.scenario == "gps_corruption":
        eta = float((primary or {}).get("eta_minutes", reasoning.get("eta_minutes", 9999.0)))
        if decision_type != "no_viable_hospital" and eta >= 9999.0:
            violations.append("unresolved_eta_after_gps_corruption")

    if case.scenario == "extreme_no_match_and_overload":
        constraints = reasoning.get("constraints_applied", []) or []
        if decision_type == "direct" and not constraints:
            violations.append("overload_no_match_constraints_not_explained")

    return violations


def _get_primary_breakdown(result: dict[str, Any], case: CaseInput | None = None) -> dict[str, float]:
    scores = result.get("ranked_candidates", [])
    if not scores:
        return {}
    breakdown = scores[0].get("score_breakdown", {}) or {}

    # Stabilization path sometimes provides legacy-only keys; derive S_* to keep
    # decision-quality scoring comparable across decision types.
    if all(key in breakdown for key in ["S_survival", "S_treatment", "S_equipment", "S_eta", "S_load"]):
        return breakdown

    reasoning = result.get("reasoning", {})
    eta = float((result.get("primary_destination") or {}).get("eta_minutes", 0.0))
    survival = float(reasoning.get("estimated_survival_time", 0.0))
    stability_score = float(reasoning.get("stability_score", 0.0))
    missing_equipment = set(reasoning.get("missing_equipment", []))

    required_count = len(case.required_equipment) if case else 0
    s_equipment = 1.0
    if required_count > 0:
        s_equipment = max(0.2, 1.0 - (len(missing_equipment) / max(1, required_count)))

    max_eta = max(5.0, float(getattr(case, "max_safe_eta", 25.0)) if case else 25.0)
    s_eta = max(0.2, min(1.0, 1.0 - (eta / max_eta)))
    s_survival = max(0.2, min(1.0, stability_score if stability_score > 0 else (survival / max(survival + eta, 1.0))))

    derived = dict(breakdown)
    derived.update(
        {
            "S_survival": float(derived.get("S_survival", s_survival)),
            "S_treatment": float(derived.get("S_treatment", 0.7 if reasoning.get("stabilization_required") else 0.8)),
            "S_equipment": float(derived.get("S_equipment", s_equipment)),
            "S_eta": float(derived.get("S_eta", s_eta)),
            "S_load": float(derived.get("S_load", 0.8)),
        }
    )
    return derived


def score_decision_from_breakdown(result: dict[str, Any], context: Any, case_input: CaseInput) -> float:
    """Quality scoring with penalties for bad judgment."""
    reasoning = result.get("reasoning", {})
    breakdown = _get_primary_breakdown(result, case_input)

    if not breakdown:
        return 0.15

    score = (
        0.30 * breakdown.get("S_survival", 0.0)
        + 0.25 * breakdown.get("S_treatment", 0.0)
        + 0.20 * breakdown.get("S_equipment", 0.0)
        + 0.15 * breakdown.get("S_eta", 0.0)
        + 0.10 * breakdown.get("S_load", 0.0)
    )

    stabilization_required = bool(reasoning.get("stabilization_required"))
    stable_hint = bool(getattr(context, "stable_hint", False))
    max_safe_eta = float(getattr(context, "max_safe_eta", 25.0))

    if stabilization_required and stable_hint:
        score -= 0.2

    required = {str(e).lower() for e in case_input.required_equipment}
    critical_required = required & {"ventilator", "defibrillator"}
    effective_equipment = {
        str(e).lower() for e in breakdown.get("effective_equipment_set", [])
    }
    if not effective_equipment:
        primary_name = (result.get("primary_destination") or {}).get("hospital_name", "")
        primary_hospital = next(
            (h for h in case_input.hospitals if h.get("hospital_id") == primary_name),
            {},
        )
        effective_equipment = {str(e).lower() for e in primary_hospital.get("equipment", [])}
        effective_equipment.update({str(e).lower() for e in case_input.ambulance_equipment})

    if critical_required and not critical_required.issubset(effective_equipment):
        score -= 0.5

    eta = float((result.get("primary_destination") or {}).get("eta_minutes", 9999))
    if eta > max_safe_eta:
        score -= 0.3

    return max(0.15, min(1.0, round(score, 4)))


def detect_borderline_decision(result: dict[str, Any]) -> bool:
    candidates = result.get("ranked_candidates", [])
    if len(candidates) < 2:
        return False
    first = float(candidates[0].get("score", 0.0))
    second = float(candidates[1].get("score", 0.0))
    return abs(first - second) < 0.05


async def oscillation_test(case: CaseInput, runs: int = 20) -> dict[str, Any]:
    """Run same input multiple times and detect instability."""
    from app.engine.dispatch_engine import run_dispatch

    kwargs = case_to_dispatch_kwargs(case)
    outputs: list[int] = []

    for _ in range(runs):
        result = await run_dispatch(**kwargs)
        primary = result.get("primary_destination") or {}
        outputs.append(int(primary.get("hospital_id", 0)))

    unique = len(set(outputs))
    return {
        "case_id": case.case_id,
        "unique_outputs": unique,
        "unstable": unique > 1,
    }


def monitor_distribution(scores: list[float]) -> list[str]:
    """Active distribution alerts for decision scores."""
    if not scores:
        return ["NO_SCORES"]

    mean = statistics.mean(scores)
    std = statistics.stdev(scores) if len(scores) > 1 else 0.0

    alerts = []
    if mean < 0.6:
        alerts.append("DEGRADATION: mean < 0.6")
    if std > 0.2:
        alerts.append("INCONSISTENT: std > 0.2")

    return alerts if alerts else ["OK"]


async def optimize_weights(
    dataset: list[ChaosCase],
    seed: int,
    max_candidates: int = 120,
) -> tuple[dict[str, float], float]:
    """Sensitive search over expanded weight space using sampled linspace combinations."""
    from app.engine.dispatch_engine import run_dispatch

    best_score = -1.0
    best_weights: dict[str, float] = {}

    rng = random.Random(seed)
    major = np.linspace(0.1, 0.5, 10)
    eta_vals = np.linspace(0.05, 0.30, 10)
    load_vals = np.linspace(0.05, 0.30, 10)

    evaluated = 0
    while evaluated < max_candidates:
        candidate = {
            "w_survival": float(rng.choice(major.tolist())),
            "w_treatment": float(rng.choice(major.tolist())),
            "w_equipment": float(rng.choice(major.tolist())),
            "w_eta": float(rng.choice(eta_vals.tolist())),
            "w_load": float(rng.choice(load_vals.tolist())),
        }
        total = sum(candidate.values())
        candidate = {k: v / total for k, v in candidate.items()}

        ACTIVE_WEIGHTS.update(candidate)

        total_score = 0.0
        for chaos_case in dataset:
            case_input = _as_case_input(chaos_case)
            kwargs = case_to_dispatch_kwargs(case_input)
            result = await run_dispatch(**kwargs)
            total_score += score_decision_from_breakdown(result, chaos_case, case_input)

        avg_score = total_score / len(dataset)
        if avg_score > best_score:
            best_score = avg_score
            best_weights = candidate
        evaluated += 1

    return best_weights, best_score


async def run_chaos_pipeline(n: int = 1000, seeds: list[int] | None = None) -> dict[str, Any]:
    """Full trust pipeline execution across multiple seeds."""
    from app.engine.dispatch_engine import run_dispatch

    logging.getLogger("app.engine.ml_scorer").setLevel(logging.ERROR)

    seeds = seeds or [13, 37, 73]

    print("\nTRUST PIPELINE")
    print("=" * 60)

    weight_runs: list[dict[str, float]] = []
    run_scores: list[float] = []
    run_oscillation: list[float] = []

    for seed in seeds:
        random.seed(seed)
        dataset = generate_dataset(n)

        scores: list[float] = []
        failures: dict[str, int] = {name: 0 for name in FAILURE_CATEGORIES}
        results: list[dict[str, Any]] = []
        borderline_cases: list[dict[str, Any]] = []

        for chaos_case in dataset:
            case_input = _as_case_input(chaos_case)
            kwargs = case_to_dispatch_kwargs(case_input)
            result = await run_dispatch(**kwargs)
            breakdown = _get_primary_breakdown(result, case_input)
            score = score_decision_from_breakdown(result, chaos_case, case_input)
            primary = result.get("primary_destination") or {}
            primary_name = primary.get("hospital_name", "")
            primary_hospital = next(
                (h for h in case_input.hospitals if h.get("hospital_id") == primary_name),
                {},
            )

            scores.append(score)
            failure_type = classify_failure(
                result=result,
                breakdown=breakdown,
                case=case_input,
                primary_hospital=primary_hospital,
            )
            failures[failure_type] = failures.get(failure_type, 0) + 1

            if detect_borderline_decision(result):
                borderline_cases.append(
                    {
                        "case_id": chaos_case.case_id,
                        "score_best": float(result.get("ranked_candidates", [{}])[0].get("score", 0.0)),
                        "score_second": float(result.get("ranked_candidates", [{}, {}])[1].get("score", 0.0))
                        if len(result.get("ranked_candidates", [])) > 1
                        else 0.0,
                    }
                )

            results.append({
                "case_id": chaos_case.case_id,
                "score": score,
                "failure": failure_type,
                "decision_type": result.get("decision_type", "unknown"),
                "primary_destination": primary_name,
                "reasoning": result.get("reasoning", {}),
                "breakdown": breakdown,
            })

        alerts = monitor_distribution(scores)

        # Oscillation test on 50 random cases
        sample_cases = random.sample(dataset, k=min(50, len(dataset)))
        unstable_count = 0
        for chaos_case in sample_cases:
            case_input = _as_case_input(chaos_case)
            osc_result = await oscillation_test(case_input, runs=20)
            if osc_result["unstable"]:
                unstable_count += 1

        oscillation_rate = unstable_count / len(sample_cases) if sample_cases else 0.0
        run_oscillation.append(oscillation_rate)

        # Weight optimization (run 3x for stability test)
        best_weights, best_score = await optimize_weights(
            random.sample(dataset, k=min(200, len(dataset))),
            seed=seed,
        )
        weight_runs.append(best_weights)

        # Worst 10 cases
        worst_cases = sorted(results, key=lambda x: x["score"])[:10]
        run_scores.append(statistics.mean(scores))

        top_failures = sorted(failures.items(), key=lambda x: x[1], reverse=True)[:3]

        print(f"\nSeed: {seed}")
        print(f"  Mean score: {statistics.mean(scores):.4f}")
        print(f"  Min score: {min(scores):.4f}")
        print(f"  Std dev: {statistics.stdev(scores):.4f}")
        print(f"  Oscillation rate: {oscillation_rate:.2%}")
        print(f"  Top failure types: {top_failures}")
        print(f"  Failure distribution: {failures}")
        print(f"  Borderline decisions: {len(borderline_cases)}")
        print("  Top 10 worst cases:")
        for item in worst_cases:
            print(
                "    - "
                f"{item['case_id']} score={item['score']:.4f} failure={item['failure']} "
                f"decision={item['decision_type']} dest={item['primary_destination']}"
            )
            print(f"      breakdown={item['breakdown']}")
            print(f"      reasoning={item['reasoning']}")
        print(f"  Alerts: {', '.join(alerts)}")
        print(f"  Optimized weights: {best_weights}  (score {best_score:.4f})")

    print("\nWEIGHT STABILITY (3 runs)")
    for idx, weights in enumerate(weight_runs, start=1):
        print(f"  Run {idx}: {weights}")

    if weight_runs:
        keys = ["w_survival", "w_treatment", "w_equipment", "w_eta", "w_load"]
        variance = {
            key: statistics.pvariance([weights[key] for weights in weight_runs])
            for key in keys
        }
        print(f"\nWeight variance across runs: {variance}")

    summary: dict[str, Any] = {"mode": "chaos"}
    if run_scores and run_oscillation:
        print("\nAggregate across seeds")
        print(f"  Mean Score: {statistics.mean(run_scores):.4f}")
        print(f"  Std Dev (seed means): {statistics.stdev(run_scores) if len(run_scores) > 1 else 0.0:.4f}")
        print(f"  Min Score (seed means): {min(run_scores):.4f}")
        print(f"  Oscillation Rate: {statistics.mean(run_oscillation):.2%}")

        summary = {
            "mode": "chaos",
            "mean_score": statistics.mean(run_scores),
            "std_seed_means": statistics.stdev(run_scores) if len(run_scores) > 1 else 0.0,
            "min_seed_mean": min(run_scores),
            "oscillation_rate": statistics.mean(run_oscillation),
        }

    return summary


async def run_adversarial_pipeline(n: int = 500, seeds: list[int] | None = None) -> dict[str, Any]:
    """Run adversarial robustness evaluation and report safety-focused metrics."""
    from app.engine.dispatch_engine import run_dispatch

    logging.getLogger("app.engine.ml_scorer").setLevel(logging.ERROR)

    seeds = seeds or [2026]

    print("\nADVERSARIAL TRUST PIPELINE")
    print("=" * 60)

    all_scores: list[float] = []
    all_results: list[dict[str, Any]] = []
    aggregate_failures: dict[str, int] = {name: 0 for name in FAILURE_CATEGORIES}
    aggregate_fallback_breakdown = _fallback_breakdown_template()
    total_cases = 0
    total_fallback = 0
    total_relaxed_constraints_used = 0
    total_partial_match_selected = 0
    total_safety_violations = 0
    total_crashes = 0
    improved_cases: list[dict[str, Any]] = []

    for seed in seeds:
        dataset = generate_adversarial_dataset(n=n, seed=seed)
        seed_scores: list[float] = []
        seed_failures: dict[str, int] = {name: 0 for name in FAILURE_CATEGORIES}
        seed_fallback_breakdown = _fallback_breakdown_template()
        seed_fallback = 0
        seed_relaxed_constraints_used = 0
        seed_partial_match_selected = 0
        seed_violations = 0
        seed_crashes = 0
        seed_results: list[dict[str, Any]] = []

        for adv_case in dataset:
            total_cases += 1

            # Baseline (pre-optimization behavior) for improvement reporting.
            kwargs = case_to_dispatch_kwargs(adv_case.case_input)
            scenario_ctx = dict(kwargs.get("scenario_context") or {})
            scenario_ctx.update({
                "scenario_name": adv_case.scenario,
                "priority_type": _infer_priority_type(adv_case.scenario),
                "expected_behavior": _infer_expected_behavior(adv_case.scenario),
                "conflicting_signals": _infer_conflicting_signals(adv_case.scenario),
                "uncertainty": _infer_uncertainty(adv_case.scenario),
            })
            kwargs["scenario_context"] = scenario_ctx

            if os.getenv("TRUST_TRACE_SIGNALS", "0") == "1":
                print("PIPELINE:", scenario_ctx)
            try:
                baseline_result = await run_dispatch(**kwargs, enable_adaptive_constraints=False)
                baseline_score = score_decision_from_breakdown(baseline_result, adv_case.case_input, adv_case.case_input)
                baseline_fallback = _is_fallback_decision(baseline_result)
            except (RuntimeError, ValueError, TypeError, KeyError):
                baseline_result = {
                    "decision_type": "crash",
                    "reasoning": {},
                }
                baseline_score = 0.15
                baseline_fallback = True

            try:
                result = await run_dispatch(**kwargs)
            except (RuntimeError, ValueError, TypeError, KeyError) as exc:
                seed_crashes += 1
                total_crashes += 1
                seed_violations += 1
                total_safety_violations += 1

                fallback_used = True
                failure_type = "input_conflict"
                score = 0.15
                safety_violations = ["dispatch_crash"]
                result = {
                    "decision_type": "crash",
                    "primary_destination": None,
                    "reasoning": {
                        "error": str(exc),
                        "fallback_triggers": ["no_viable_hospital_after_constraints"],
                    },
                    "ranked_candidates": [],
                }
                breakdown = {}
                primary_name = ""
            else:
                breakdown = _get_primary_breakdown(result, adv_case.case_input)
                score = score_decision_from_breakdown(result, adv_case.case_input, adv_case.case_input)
                primary = result.get("primary_destination") or {}
                primary_name = str(primary.get("hospital_name", ""))
                primary_hospital = next(
                    (h for h in adv_case.case_input.hospitals if h.get("hospital_id") == primary_name),
                    {},
                )

                failure_type = classify_failure(
                    result=result,
                    breakdown=breakdown,
                    case=adv_case.case_input,
                    primary_hospital=primary_hospital,
                )
                if failure_type not in FAILURE_CATEGORIES:
                    failure_type = "input_conflict"

                fallback_used = _is_fallback_decision(result)
                safety_violations = _validate_adversarial_safety(
                    case=adv_case,
                    result=result,
                    score=score,
                    failure_type=failure_type,
                )

                if safety_violations:
                    seed_violations += len(safety_violations)
                    total_safety_violations += len(safety_violations)

            reasoning = result.get("reasoning", {}) or {}
            if reasoning.get("relaxed_constraints_mode"):
                seed_relaxed_constraints_used += 1
                total_relaxed_constraints_used += 1
            if reasoning.get("partial_match_selected"):
                seed_partial_match_selected += 1
                total_partial_match_selected += 1

            if fallback_used:
                seed_fallback += 1
                total_fallback += 1
                for key in _extract_fallback_breakdown_keys(result):
                    seed_fallback_breakdown[key] = seed_fallback_breakdown.get(key, 0) + 1
                    aggregate_fallback_breakdown[key] = aggregate_fallback_breakdown.get(key, 0) + 1

            seed_scores.append(score)
            all_scores.append(score)
            seed_failures[failure_type] = seed_failures.get(failure_type, 0) + 1
            aggregate_failures[failure_type] = aggregate_failures.get(failure_type, 0) + 1

            if (score - baseline_score) > 0.0 or (baseline_fallback and not fallback_used):
                improved_cases.append(
                    {
                        "case_id": adv_case.case_input.case_id,
                        "scenario": adv_case.scenario,
                        "score_before": baseline_score,
                        "score_after": score,
                        "score_delta": round(score - baseline_score, 4),
                        "fallback_before": baseline_fallback,
                        "fallback_after": fallback_used,
                        "triggers_before": _extract_fallback_breakdown_keys(baseline_result),
                        "triggers_after": _extract_fallback_breakdown_keys(result),
                    }
                )

            item = {
                "case_id": adv_case.case_input.case_id,
                "scenario": adv_case.scenario,
                "notes": adv_case.notes,
                "score": score,
                "failure": failure_type,
                "fallback_used": fallback_used,
                "decision_type": result.get("decision_type", "unknown"),
                "primary_destination": primary_name,
                "reasoning": result.get("reasoning", {}),
                "breakdown": breakdown,
                "safety_violations": safety_violations,
            }
            seed_results.append(item)
            all_results.append(item)

        seed_min = min(seed_scores) if seed_scores else 0.0
        seed_mean = statistics.mean(seed_scores) if seed_scores else 0.0
        seed_fallback_rate = (seed_fallback / len(dataset)) if dataset else 0.0
        seed_relaxed_rate = (seed_relaxed_constraints_used / len(dataset)) if dataset else 0.0
        seed_partial_rate = (seed_partial_match_selected / len(dataset)) if dataset else 0.0

        print(f"\nSeed: {seed}")
        print(f"  Cases: {len(dataset)}")
        print(f"  Mean score: {seed_mean:.4f}")
        print(f"  Min score: {seed_min:.4f}")
        print(f"  Failure distribution: {seed_failures}")
        print(f"  Fallback usage rate: {seed_fallback_rate:.2%}")
        print(f"  Fallback breakdown: {seed_fallback_breakdown}")
        print(f"  Relaxed constraints usage rate: {seed_relaxed_rate:.2%}")
        print(f"  Partial match selection rate: {seed_partial_rate:.2%}")
        print(f"  Safety violations: {seed_violations}")
        print(f"  Crashes: {seed_crashes}")

    worst_cases = sorted(all_results, key=lambda x: x["score"])[:10]

    overall_mean = statistics.mean(all_scores) if all_scores else 0.0
    overall_min = min(all_scores) if all_scores else 0.0
    fallback_usage_rate = (total_fallback / total_cases) if total_cases else 0.0
    relaxed_constraint_usage_rate = (total_relaxed_constraints_used / total_cases) if total_cases else 0.0
    partial_match_selection_rate = (total_partial_match_selected / total_cases) if total_cases else 0.0
    top_10_improved = sorted(
        improved_cases,
        key=lambda item: (
            1 if item["fallback_before"] and not item["fallback_after"] else 0,
            item["score_delta"],
        ),
        reverse=True,
    )[:10]

    print("\nADVERSARIAL REPORT")
    print("-" * 60)
    print(f"Mean score: {overall_mean:.4f}")
    print(f"Min score: {overall_min:.4f}")
    print(f"Failure distribution: {aggregate_failures}")
    print(f"Fallback usage rate: {fallback_usage_rate:.2%}")
    print(f"Fallback breakdown: {aggregate_fallback_breakdown}")
    print(f"Relaxed constraints usage rate: {relaxed_constraint_usage_rate:.2%}")
    print(f"Partial match selection rate: {partial_match_selection_rate:.2%}")
    print(f"Safety violations: {total_safety_violations}")
    print(f"Crashes: {total_crashes}")
    print("Top 10 worst adversarial cases:")
    for item in worst_cases:
        print(
            "  - "
            f"{item['case_id']} scenario={item['scenario']} score={item['score']:.4f} "
            f"failure={item['failure']} fallback={item['fallback_used']} "
            f"decision={item['decision_type']} dest={item['primary_destination']}"
        )
        print(f"    notes={item['notes']}")
        print(f"    breakdown={item['breakdown']}")
        print(f"    reasoning={item['reasoning']}")
        print(f"    safety_violations={item['safety_violations']}")

    print("Top 10 improved cases (before vs after fallback reduction):")
    for item in top_10_improved:
        print(
            "  - "
            f"{item['case_id']} scenario={item['scenario']} "
            f"before={item['score_before']:.4f} after={item['score_after']:.4f} "
            f"delta={item['score_delta']:.4f} "
            f"fallback_before={item['fallback_before']} fallback_after={item['fallback_after']}"
        )
        print(f"    triggers_before={item['triggers_before']} triggers_after={item['triggers_after']}")

    return {
        "mode": "adversarial",
        "mean_score": overall_mean,
        "min_score": overall_min,
        "failure_distribution": aggregate_failures,
        "fallback_usage_rate": fallback_usage_rate,
        "fallback_breakdown": aggregate_fallback_breakdown,
        "relaxed_constraint_usage_rate": relaxed_constraint_usage_rate,
        "partial_match_selection_rate": partial_match_selection_rate,
        "safety_violations": total_safety_violations,
        "crashes": total_crashes,
        "top_10_worst": worst_cases,
        "top_10_improved": top_10_improved,
    }


async def run_trust_pipeline(
    n: int = 1000,
    seeds: list[int] | None = None,
    mode: str = "chaos",
) -> dict[str, Any]:
    mode = mode.strip().lower()
    if mode == "adversarial":
        return await run_adversarial_pipeline(n=max(500, n), seeds=seeds)
    return await run_chaos_pipeline(n=n, seeds=seeds)


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trust validation pipelines")
    parser.add_argument("--mode", choices=["chaos", "adversarial"], default="chaos")
    parser.add_argument("--n", type=int, default=1000, help="Case count")
    parser.add_argument(
        "--seeds",
        type=str,
        default="",
        help="Comma-separated integer seeds (example: 13,37,73)",
    )
    return parser.parse_args()


def _parse_seed_list(seed_arg: str) -> list[int] | None:
    if not seed_arg.strip():
        return None
    parsed: list[int] = []
    for token in seed_arg.split(","):
        token = token.strip()
        if not token:
            continue
        parsed.append(int(token))
    return parsed or None


if __name__ == "__main__":
    args = _parse_cli_args()
    parsed_seeds = _parse_seed_list(args.seeds)
    asyncio.run(run_trust_pipeline(n=args.n, seeds=parsed_seeds, mode=args.mode))
