"""
Real Trust Layer — Wired to Actual Dispatch Engine
==================================================

This module replaces demo stubs with real implementations that:
1. Call run_dispatch with real hospital data
2. Tune weights that ml_scorer.py reads from ACTIVE_WEIGHTS
3. Run oscillation stress tests against the real engine
4. Report quality scores from real decision breakdowns

Usage:
  python -m tests.trust_layer
"""

import asyncio
import statistics
from dataclasses import dataclass
from typing import Any

from tests.validation_harness import (
    SyntheticCaseGenerator,
    CaseInput,
)


# ============================================================================
# WEIGHT REGISTRY — ml_scorer.py must import this dict instead of hardcoding
# ============================================================================

ACTIVE_WEIGHTS: dict[str, float] = {
    "w_survival": 0.30,
    "w_treatment": 0.25,
    "w_equipment": 0.20,
    "w_eta": 0.15,
    "w_load": 0.10,
}


# ============================================================================
# CASE ADAPTER — convert CaseInput -> run_dispatch kwargs
# ============================================================================

def case_to_dispatch_kwargs(case: CaseInput) -> dict[str, Any]:
    """
    Convert a CaseInput from the test harness into kwargs for run_dispatch.

    Maps hospital dicts from the test format to the format get_latest_hospital_snapshots
    returns, so the same engine code runs against synthetic data.
    """
    hospitals = []
    for hospital in case.hospitals:
        name = hospital.get("hospital_id", "unknown")
        hashed_id = abs(hash(name)) % 10_000
        lat_offset = (hash(name) % 100) * 0.001
        lng_offset = (hash(name) % 100) * 0.001
        latitude = hospital.get("latitude", hospital.get("lat", 30.3165 + lat_offset))
        longitude = hospital.get("longitude", hospital.get("lng", 78.0322 + lng_offset))
        available_beds = int(hospital.get("available_beds", hospital.get("beds", 0)))
        total_beds = int(hospital.get("total_beds", max(available_beds, 1)))

        hospitals.append({
            "id": hashed_id,
            "name": name,
            "address": "",
            "latitude": float(latitude),
            "longitude": float(longitude),
            "available_beds": available_beds,
            "icu_beds": int(hospital.get("icu_beds", 0)),
            "equipment": [str(e).strip().lower() for e in hospital.get("equipment", [])],
            "accepting": bool(hospital.get("accepting", True)),
            "specialists": {},
            "specialist_count": 0,
            "data_source": "synthetic",
            "last_updated": hospital.get("last_updated"),
            "hospital_type": hospital.get("hospital_type", "both"),
            "has_icu": bool(hospital.get("has_icu", False)),
            "eta_minutes": float(hospital.get("eta_minutes", 10.0)),
            "hospital_load": hospital.get("hospital_load"),
            "total_beds": total_beds,
            "score": 0.0,
            "score_breakdown": {},
        })

    return dict(
        case_id=case.case_id,
        hospitals=hospitals,
        # Fixed ambulance location — ETAs derive from hospital coords
        ambulance_lat=30.3165,
        ambulance_lng=78.0322,
        condition_type=case.condition,
        severity_score=case.severity_score,
        vitals=case.patient_vitals,
        ambulance_equipment=case.ambulance_equipment,
        required_equipment=case.required_equipment,
        scenario_context={
            "scenario_name": str(getattr(case, "scenario_name", "") or ""),
            "priority_type": str(getattr(case, "priority_type", "") or ""),
            "expected_behavior": str(getattr(case, "expected_behavior", "") or ""),
            "conflicting_signals": bool(getattr(case, "conflicting_signals", False)),
            "uncertainty": float(getattr(case, "uncertainty", 0.0) or 0.0),
        },
    )


# ============================================================================
# 1. REAL OSCILLATION STRESS TEST
# ============================================================================

async def run_oscillation_stress_test(
    case: CaseInput,
    runs: int = 20,
) -> dict[str, Any]:
    """
    Run the same case through run_dispatch N times.
    Any variation in decision_type or primary destination is a real bug.
    """
    from app.engine.dispatch_engine import run_dispatch

    kwargs = case_to_dispatch_kwargs(case)
    decisions: list[str] = []
    destinations: list[str] = []
    errors: list[str] = []
    dispatch_fn: Any = run_dispatch

    for _ in range(runs):
        try:
            result = await dispatch_fn(**kwargs)
            decisions.append(result.get("decision_type", "unknown"))
            primary = result.get("primary_destination") or {}
            destinations.append(primary.get("hospital_name", "none"))
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            errors.append(str(exc))

    unique_decisions = sorted(set(decisions))
    unique_destinations = sorted(set(destinations))
    oscillating = len(unique_decisions) > 1 or len(unique_destinations) > 1

    return {
        "case_id": case.case_id,
        "runs": runs,
        "errors": len(errors),
        "oscillating": oscillating,
        "status": "NON-DETERMINISTIC" if oscillating else "Consistent",
        "unique_decisions": unique_decisions,
        "unique_destinations": unique_destinations,
    }


async def stress_test_all_cases(runs_per_case: int = 20) -> dict[str, Any]:
    """Run oscillation stress test across all 40 cases."""
    cases = SyntheticCaseGenerator.generate_all_cases()
    results = []
    oscillating_cases = []

    print(f"\nOSCILLATION STRESS TEST ({len(cases)} cases x {runs_per_case} runs each)")
    print("=" * 70)

    for case in cases:
        result = await run_oscillation_stress_test(case, runs=runs_per_case)
        results.append(result)
        status = result["status"]
        print(f"  {case.case_id[:45]:<45} {status}")
        if result["oscillating"]:
            oscillating_cases.append(result)

    print(f"\n  Total: {len(cases)} cases")
    print(f"  Consistent: {len(cases) - len(oscillating_cases)}")
    print(f"  Oscillating: {len(oscillating_cases)}")

    return {
        "total_cases": len(cases),
        "oscillating_count": len(oscillating_cases),
        "oscillating_cases": oscillating_cases,
        "all_results": results,
    }


# ============================================================================
# 2. REAL DECISION QUALITY SCORING
# ============================================================================

def score_decision_quality(result: dict[str, Any], case: CaseInput) -> float:
    """
    Score the quality of a real dispatch result on a 0-1 scale.

    Dimensions:
      - Equipment coverage for required equipment (0-1)
      - Survival margin (0-1)
      - Stability score threshold (0-1)
      - ETA efficiency vs best candidate (0-1)
    """
    if result.get("decision_type") == "no_viable_hospital":
        return 0.0

    reasoning = result.get("reasoning", {})
    primary = result.get("primary_destination") or {}
    candidates = result.get("ranked_candidates", [])

    scores: list[float] = []

    # Equipment coverage
    primary_name = primary.get("hospital_name", "")
    primary_hospital = next(
        (h for h in case.hospitals if h.get("hospital_id") == primary_name), {}
    )
    primary_equip = {str(e).lower() for e in primary_hospital.get("equipment", [])}
    required = {str(e).lower() for e in case.required_equipment}
    if required:
        coverage = len(required & primary_equip) / len(required)
    else:
        coverage = 1.0
    scores.append(coverage)

    # Survival margin
    survival = float(reasoning.get("estimated_survival_time", 0))
    eta = float(primary.get("eta_minutes", 9999))
    if survival > 0 and eta > 0:
        margin = min(1.0, survival / (survival + eta))
    else:
        margin = 0.5
    scores.append(margin)

    # Stability score threshold
    stability = float(reasoning.get("stability_score", 0))
    scores.append(min(1.0, stability / 0.6))

    # ETA efficiency — is this the lowest-ETA viable candidate?
    all_etas = [float(c.get("eta_minutes", 9999)) for c in candidates]
    if all_etas:
        best_eta = min(all_etas)
        eta_efficiency = best_eta / max(eta, 0.1)
        scores.append(min(1.0, eta_efficiency))
    else:
        scores.append(0.5)

    return round(sum(scores) / len(scores), 4)


# ============================================================================
# 3. REAL DISTRIBUTION ALERT SYSTEM
# ============================================================================

class LiveDistributionMonitor:
    """
    Collects real score_breakdown dicts from ranked_candidates and alerts
    when weight dominance or score collapse is detected.
    """

    def __init__(self) -> None:
        self.component_samples: dict[str, list[float]] = {
            "S_survival": [],
            "S_treatment": [],
            "S_equipment": [],
            "S_eta": [],
            "S_load": [],
        }
        self.final_scores: list[float] = []

    def ingest_result(self, result: dict[str, Any]) -> None:
        """Pull score breakdowns from all ranked candidates in a result."""
        for candidate in result.get("ranked_candidates", []):
            breakdown = candidate.get("score_breakdown", {})
            for key in self.component_samples:
                val = breakdown.get(key)
                if isinstance(val, (int, float)):
                    self.component_samples[key].append(float(val))
            score = candidate.get("score")
            if isinstance(score, (int, float)):
                self.final_scores.append(float(score))

    def generate_alerts(self) -> list[str]:
        alerts: list[str] = []
        populated = {k: v for k, v in self.component_samples.items() if len(v) >= 3}

        if not populated:
            return [
                "NO_DATA: score_breakdown not populated in ranked_candidates — check ml_scorer.py"
            ]

        means = {k: statistics.mean(v) for k, v in populated.items()}
        overall_mean = statistics.mean(means.values())

        for component, mean_val in means.items():
            gap = abs(mean_val - overall_mean)
            if gap > 0.20:
                alerts.append(
                    f"DOMINANCE: {component} mu={mean_val:.3f}  gap={gap:.3f} > 0.20"
                )

        for component, values in populated.items():
            if len(values) > 2:
                stdev = statistics.stdev(values)
                if stdev < 0.05:
                    alerts.append(
                        f"NEAR_CONSTANT: {component} sigma={stdev:.4f}  always ~ {statistics.mean(values):.3f}"
                    )

        if len(self.final_scores) >= 3:
            fs_stdev = statistics.stdev(self.final_scores)
            if fs_stdev < 0.05:
                alerts.append(
                    f"SCORE_COLLAPSE: final_score sigma={fs_stdev:.4f}  — random tie-breaking likely"
                )

        return alerts if alerts else ["OK: No distribution anomalies detected"]


# ============================================================================
# 4. REAL AUTO-WEIGHT OPTIMIZER
# ============================================================================

@dataclass
class WeightEvalResult:
    weights: dict[str, float]
    pass_count: int
    avg_quality: float
    composite_score: float


async def _evaluate_weight_set(
    weights: dict[str, float],
    cases: list[CaseInput],
    forbidden_map: dict[str, list[str]],
) -> WeightEvalResult:
    """Run all cases with given weights and compute composite score."""
    from app.engine.dispatch_engine import run_dispatch

    ACTIVE_WEIGHTS.update(weights)

    pass_count = 0
    quality_sum = 0.0
    dispatch_fn: Any = run_dispatch

    for case in cases:
        kwargs = case_to_dispatch_kwargs(case)
        try:
            result = await dispatch_fn(**kwargs)
        except (RuntimeError, ValueError, TypeError, KeyError):
            continue

        primary = (result.get("primary_destination") or {}).get("hospital_name", "")
        forbidden = forbidden_map.get(case.case_id, [])

        avoided_forbidden = primary not in forbidden
        quality = score_decision_quality(result, case)

        if avoided_forbidden and quality >= 0.60:
            pass_count += 1
        quality_sum += quality

    n = len(cases)
    avg_q = quality_sum / n if n else 0.0
    composite = (pass_count / n) * 0.7 + avg_q * 0.3 if n else 0.0

    return WeightEvalResult(
        weights=weights.copy(),
        pass_count=pass_count,
        avg_quality=avg_q,
        composite_score=composite,
    )


def _renormalize(weights: dict[str, float]) -> dict[str, float]:
    total = sum(weights.values())
    return {k: round(v / total, 6) for k, v in weights.items()}


async def optimize_weights(
    cases: list[CaseInput] | None = None,
    forbidden_map: dict[str, list[str]] | None = None,
    max_iterations: int = 80,
) -> dict[str, Any]:
    """
    Grid search over weight space to maximize (pass_rate * 0.7 + avg_quality * 0.3).

    Varies one weight at a time around the baseline, renormalizes after each
    perturbation so weights always sum to 1.0.
    """
    if cases is None:
        cases = SyntheticCaseGenerator.generate_all_cases()
    if forbidden_map is None:
        from tests.validation_harness import ExpectationLibrary
        forbidden_map = {
            case_id: exp.must_not_choose
            for case_id, exp in ExpectationLibrary.EXPECTATIONS.items()
        }

    baseline = {
        "w_survival": 0.30,
        "w_treatment": 0.25,
        "w_equipment": 0.20,
        "w_eta": 0.15,
        "w_load": 0.10,
    }

    best: WeightEvalResult | None = None
    history: list[dict] = []
    iteration = 0

    print(f"\nWEIGHT OPTIMIZER  ({len(cases)} cases, max {max_iterations} iterations)")
    print("=" * 70)

    async def _eval_and_record(weight_set: dict[str, float]) -> WeightEvalResult:
        nonlocal iteration, best
        normed = _renormalize(weight_set)
        evr = await _evaluate_weight_set(normed, cases, forbidden_map)
        history.append({
            "iteration": iteration,
            "weights": normed,
            "pass_count": evr.pass_count,
            "avg_quality": round(evr.avg_quality, 4),
            "composite": round(evr.composite_score, 4),
        })
        if best is None or evr.composite_score > best.composite_score:
            best = evr
        if iteration % 10 == 0:
            print(
                f"  [{iteration:3d}] composite={evr.composite_score:.4f}  "
                f"passes={evr.pass_count}/{len(cases)}  "
                f"avg_q={evr.avg_quality:.4f}"
            )
        iteration += 1
        return evr

    await _eval_and_record(baseline)

    deltas = [-0.08, -0.04, -0.02, 0.02, 0.04, 0.08]
    for weight_name in baseline:
        for delta in deltas:
            if iteration >= max_iterations:
                break
            candidate = baseline.copy()
            candidate[weight_name] = max(0.02, baseline[weight_name] + delta)
            await _eval_and_record(candidate)
        if iteration >= max_iterations:
            break

    if best:
        ACTIVE_WEIGHTS.update(best.weights)

    best_composite = best.composite_score if best else 0.0
    best_passes = best.pass_count if best else 0
    best_weights = best.weights if best else baseline

    print(f"\n  Best composite: {best_composite:.4f}")
    print(f"  Best passes   : {best_passes}/{len(cases)}")
    print(f"  Best weights  : {best_weights}")

    return {
        "best_weights": best_weights,
        "best_composite": best_composite,
        "best_pass_count": best_passes,
        "history": history,
    }


# ============================================================================
# 5. FULL TRUST REPORT
# ============================================================================

async def run_full_trust_report() -> None:
    """Run all trust checks and print a unified report."""
    from app.engine.dispatch_engine import run_dispatch

    cases = SyntheticCaseGenerator.generate_all_cases()
    monitor = LiveDistributionMonitor()
    quality_scores: list[float] = []

    print("\n" + "=" * 70)
    print("MEDIROUTE TRUST LAYER — FULL REPORT")
    print("=" * 70)

    # Run all cases, collect quality + distribution
    print(f"\nRunning {len(cases)} cases through dispatch engine...")
    pass_count = 0
    dispatch_fn: Any = run_dispatch
    for case in cases:
        kwargs = case_to_dispatch_kwargs(case)
        try:
            result = await dispatch_fn(**kwargs)
            monitor.ingest_result(result)
            quality = score_decision_quality(result, case)
            quality_scores.append(quality)
            if quality >= 0.60:
                pass_count += 1
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            print(f"  ERROR {case.case_id}: {exc}")
            quality_scores.append(0.0)

    avg_quality = statistics.mean(quality_scores) if quality_scores else 0.0

    print(f"\n  Pass rate   : {pass_count}/{len(cases)} ({100*pass_count/len(cases):.1f}%)")
    print(f"  Avg quality : {avg_quality:.4f}")
    print(f"  Min quality : {min(quality_scores):.4f}")
    print(f"  Max quality : {max(quality_scores):.4f}")

    # Distribution alerts
    print("\nDISTRIBUTION ALERTS")
    print("-" * 70)
    for alert in monitor.generate_alerts():
        print(f"  {alert}")

    # Oscillation (5 cases x 10 runs for speed)
    print("\nOSCILLATION CHECK (5 critical cases x 10 runs)")
    print("-" * 70)
    critical_cases = cases[:5]
    for case in critical_cases:
        result = await run_oscillation_stress_test(case, runs=10)
        print(f"  {case.case_id[:50]:<50} {result['status']}")

    # Summary
    print("\n" + "=" * 70)
    print("TRUST SUMMARY")
    print("=" * 70)
    distribution_ok = all("OK" in a for a in monitor.generate_alerts())
    print(f"  Pass rate     : {100*pass_count/len(cases):.1f}%  {'OK' if pass_count/len(cases) >= 0.80 else 'WARN'}")
    print(f"  Avg quality   : {avg_quality:.3f}  {'OK' if avg_quality >= 0.60 else 'WARN'}")
    print(f"  Distribution : {'OK' if distribution_ok else 'WARN'}")
    print()


if __name__ == "__main__":
    asyncio.run(run_full_trust_report())
