"""CLI entrypoint for scenario simulation validation."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from pathlib import Path
from typing import Any

from simulation.scenario_evaluator import ScenarioEvaluator
from simulation.scenario_library import list_scenarios


LAST_REPORT_PATH = Path(__file__).resolve().parent / "artifacts" / "last_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scenario-based dispatch simulation and intelligence report.")
    parser.add_argument("--seed", type=int, default=42, help="Base seed for deterministic generation.")
    parser.add_argument("--cases", type=int, default=100, help="Cases per scenario.")
    parser.add_argument("--n", type=int, default=None, help="Alias for --cases.")
    parser.add_argument("--seeds", type=int, default=1, help="Run N sequential seeds and aggregate results.")
    parser.add_argument(
        "--failure-threshold",
        type=float,
        default=0.10,
        help="Failure-rate threshold that triggers targeted learning update.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        dest="scenarios",
        default=[],
        help="Scenario name to run. Repeat for multiple scenarios. Defaults to all scenarios.",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        default="",
        help="Optional baseline JSON report to compare against. Defaults to previous run snapshot.",
    )
    parser.add_argument(
        "--offline-eta",
        action="store_true",
        help="Force haversine ETA fallback for deterministic and faster simulation runs.",
    )
    parser.add_argument("--output", type=str, default="", help="Optional JSON output path.")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if bool(args.offline_eta):
        from app.services import eta_service

        eta_service.set_haversine_only_mode(True)

    cases = int(args.n) if args.n is not None else int(args.cases)
    seeds = max(1, int(args.seeds))
    selected = args.scenarios or list_scenarios()
    seed_reports: list[dict[str, Any]] = []

    for index in range(seeds):
        evaluator = ScenarioEvaluator(seed=int(args.seed) + index, failure_threshold=args.failure_threshold)
        seed_reports.append(await evaluator.evaluate_all(cases_per_scenario=cases, scenario_names=selected))

    return _aggregate_seed_reports(seed_reports, cases_per_scenario=cases)


def _aggregate_seed_reports(seed_reports: list[dict[str, Any]], *, cases_per_scenario: int) -> dict[str, Any]:
    scenarios = sorted({name for payload in seed_reports for name in (payload.get("scenarios") or {}).keys()})
    aggregated_scenarios: dict[str, Any] = {}

    for scenario_name in scenarios:
        reports = [payload.get("scenarios", {}).get(scenario_name) for payload in seed_reports]
        reports = [item for item in reports if isinstance(item, dict)]
        if not reports:
            continue

        metrics_keys = [
            "scenario_mean_score",
            "scenario_mean_raw_score",
            "scenario_failure_rate",
            "fallback_rate",
            "correct_behavior_rate",
            "behavior_mismatch_rate",
            "mismatch_penalty_impact",
        ]
        metrics: dict[str, float] = {}
        for key in metrics_keys:
            values = [float((item.get("metrics") or {}).get(key, 0.0)) for item in reports]
            metrics[key] = round(statistics.fmean(values) if values else 0.0, 6)

        failure_breakdown: dict[str, int] = {}
        for item in reports:
            for failure_name, count in (item.get("failure_breakdown") or {}).items():
                failure_breakdown[failure_name] = failure_breakdown.get(failure_name, 0) + int(count)

        aggregated_scenarios[scenario_name] = {
            "scenario": scenario_name,
            "priority_type": reports[0].get("priority_type"),
            "expected_behavior": reports[0].get("expected_behavior"),
            "total_cases": sum(int(item.get("total_cases", 0)) for item in reports),
            "metrics": metrics,
            "dominant_failure_mode": max(
                failure_breakdown.items(),
                key=lambda item: item[1],
                default=("none", 0),
            )[0],
            "failure_breakdown": failure_breakdown,
            "failure_mode_reweighting": reports[-1].get("failure_mode_reweighting") or {},
            "scenario_adjustment_profile": reports[-1].get("scenario_adjustment_profile"),
            "targeted_learning_update": reports[-1].get("targeted_learning_update"),
            "mismatch_alerts": reports[-1].get("mismatch_alerts") or [],
            "worst_cases": reports[-1].get("worst_cases") or [],
        }

    overall_mean_scores = [float((item.get("overall") or {}).get("mean_scenario_score", 0.0)) for item in seed_reports]
    overall_failure = [float((item.get("overall") or {}).get("mean_failure_rate", 0.0)) for item in seed_reports]
    overall_mismatch = [float((item.get("overall") or {}).get("mean_behavior_mismatch_rate", 0.0)) for item in seed_reports]
    overall_min_score = [float((item.get("overall") or {}).get("min_observed_score", 0.0)) for item in seed_reports]
    overall_safety_violations = [int((item.get("overall") or {}).get("total_safety_violations", 0)) for item in seed_reports]
    overall_crashes = [int((item.get("overall") or {}).get("total_crashes", 0)) for item in seed_reports]

    return {
        "seed": int(seed_reports[0].get("seed", 42)) if seed_reports else 42,
        "seeds": [int(item.get("seed", 0)) for item in seed_reports],
        "failure_threshold": float(seed_reports[0].get("failure_threshold", 0.10)) if seed_reports else 0.10,
        "cases_per_scenario": int(cases_per_scenario),
        "overall": {
            "mean_scenario_score": round(statistics.fmean(overall_mean_scores) if overall_mean_scores else 0.0, 6),
            "mean_failure_rate": round(statistics.fmean(overall_failure) if overall_failure else 0.0, 6),
            "mean_behavior_mismatch_rate": round(statistics.fmean(overall_mismatch) if overall_mismatch else 0.0, 6),
            "min_observed_score": round(min(overall_min_score) if overall_min_score else 0.0, 6),
            "scenario_count": len(aggregated_scenarios),
            "total_safety_violations": int(sum(overall_safety_violations)),
            "total_crashes": int(sum(overall_crashes)),
            "target_check": {
                "mean_score_gte_075": (statistics.fmean(overall_mean_scores) if overall_mean_scores else 0.0) >= 0.75,
                "failure_rate_lte_020": (statistics.fmean(overall_failure) if overall_failure else 1.0) <= 0.20,
                "behavior_mismatch_lte_010": (statistics.fmean(overall_mismatch) if overall_mismatch else 1.0) <= 0.10,
                "min_score_gte_015": (min(overall_min_score) if overall_min_score else 0.0) >= 0.15,
                "no_safety_violations": sum(overall_safety_violations) == 0,
                "no_crashes": sum(overall_crashes) == 0,
            },
        },
        "scenarios": aggregated_scenarios,
        "seed_reports": seed_reports,
    }


def _load_baseline(path: str) -> dict[str, Any] | None:
    candidate_path = Path(path) if path else LAST_REPORT_PATH
    if not candidate_path.exists():
        return None
    try:
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _comparison(current: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any] | None:
    if not baseline:
        return None

    cur_overall = current.get("overall") or {}
    base_overall = baseline.get("overall") or {}
    return {
        "overall_delta": {
            "mean_scenario_score": round(float(cur_overall.get("mean_scenario_score", 0.0)) - float(base_overall.get("mean_scenario_score", 0.0)), 6),
            "mean_failure_rate": round(float(cur_overall.get("mean_failure_rate", 0.0)) - float(base_overall.get("mean_failure_rate", 0.0)), 6),
            "mean_behavior_mismatch_rate": round(float(cur_overall.get("mean_behavior_mismatch_rate", 0.0)) - float(base_overall.get("mean_behavior_mismatch_rate", 0.0)), 6),
            "min_observed_score": round(float(cur_overall.get("min_observed_score", 0.0)) - float(base_overall.get("min_observed_score", 0.0)), 6),
        }
    }


def _print_report(payload: dict[str, Any]) -> None:
    overall = payload.get("overall", {})
    comparison = payload.get("comparison") or {}
    target_check = overall.get("target_check") or {}

    print("SCENARIO SIMULATION REPORT")
    print("=" * 80)
    print(
        f"Seeds={payload.get('seeds')} cases_per_scenario={payload.get('cases_per_scenario')} "
        f"failure_threshold={payload.get('failure_threshold')}"
    )
    print(
        f"Overall mean_score={overall.get('mean_scenario_score', 0.0):.4f} "
        f"mean_failure_rate={overall.get('mean_failure_rate', 0.0):.4f} "
        f"mean_behavior_mismatch_rate={overall.get('mean_behavior_mismatch_rate', 0.0):.4f} "
        f"min_observed_score={overall.get('min_observed_score', 0.0):.4f} "
        f"safety_violations={int(overall.get('total_safety_violations', 0))} "
        f"crashes={int(overall.get('total_crashes', 0))}"
    )
    print(
        "Target check: "
        f"mean>=0.75={target_check.get('mean_score_gte_075', False)} "
        f"failure<=0.20={target_check.get('failure_rate_lte_020', False)} "
        f"mismatch<=0.10={target_check.get('behavior_mismatch_lte_010', False)} "
        f"min>=0.15={target_check.get('min_score_gte_015', False)} "
        f"no_safety_violations={target_check.get('no_safety_violations', False)} "
        f"no_crashes={target_check.get('no_crashes', False)}"
    )

    if comparison:
        delta = comparison.get("overall_delta") or {}
        print(
            "Pre vs post delta: "
            f"mean_score={delta.get('mean_scenario_score', 0.0):+.4f}, "
            f"failure_rate={delta.get('mean_failure_rate', 0.0):+.4f}, "
            f"mismatch_rate={delta.get('mean_behavior_mismatch_rate', 0.0):+.4f}, "
            f"min_score={delta.get('min_observed_score', 0.0):+.4f}"
        )

    scenarios = payload.get("scenarios", {})
    for scenario_name in sorted(scenarios):
        report = scenarios[scenario_name]
        metrics = report.get("metrics", {})
        print("\n" + "-" * 80)
        print(f"Scenario: {scenario_name} ({report.get('priority_type', 'unknown')})")
        print(
            "Metrics: "
            f"mean_score={metrics.get('scenario_mean_score', 0.0):.4f}, "
            f"mean_raw_score={metrics.get('scenario_mean_raw_score', 0.0):.4f}, "
            f"failure_rate={metrics.get('scenario_failure_rate', 0.0):.4f}, "
            f"fallback_rate={metrics.get('fallback_rate', 0.0):.4f}, "
            f"correct_behavior_rate={metrics.get('correct_behavior_rate', 0.0):.4f}, "
            f"behavior_mismatch_rate={metrics.get('behavior_mismatch_rate', 0.0):.4f}, "
            f"mismatch_penalty_impact={metrics.get('mismatch_penalty_impact', 0.0):.4f}"
        )
        print(f"Failure mode: {report.get('dominant_failure_mode', 'none')}")

        reweighting = report.get("failure_mode_reweighting") or {}
        if reweighting.get("component_shifts"):
            print(f"Failure mode reweighting: {reweighting.get('component_shifts')}")

        profile = report.get("scenario_adjustment_profile") or {}
        if profile:
            print(f"Scenario weight multipliers: {(profile.get('weight_multipliers') or {})}")

        mismatches = report.get("mismatch_alerts", [])
        if mismatches:
            print("Mismatch alerts:")
            for alert in mismatches[:5]:
                print(
                    f"  - {alert.get('case_id')}: {alert.get('alert')} "
                    f"(decision={alert.get('decision_type')}, hospital={alert.get('selected_hospital')})"
                )

        print("Worst 5 cases:")
        for row in report.get("worst_cases", []):
            print(
                f"  - {row.get('case_id')}: score={row.get('score', 0.0):.4f}, "
                f"failure={row.get('failure_type')}, decision={row.get('decision_type')}, "
                f"hospital={row.get('selected_hospital')}"
            )

        learning_update = report.get("targeted_learning_update")
        if learning_update:
            print(
                f"Targeted learning update triggered at failure_rate={learning_update.get('failure_rate', 0.0):.4f} "
                f"(threshold={learning_update.get('threshold', 0.0):.4f})"
            )


def main() -> None:
    args = parse_args()
    payload = asyncio.run(_run(args))
    baseline = _load_baseline(args.baseline)
    payload["comparison"] = _comparison(payload, baseline)
    _print_report(payload)

    LAST_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
        print(f"\nJSON report written to: {output_path}")


if __name__ == "__main__":
    main()
