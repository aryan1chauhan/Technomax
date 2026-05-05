import argparse
import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _pick_metric(summary: dict, metric_name: str, default=None):
    metric = summary.get("metrics", {}).get(metric_name, {})
    values = metric.get("values", {})
    return values if values else default


def _check_thresholds(profile: str, dispatch_summary: dict, ws_summary: dict | None) -> tuple[bool, list[str]]:
    issues: list[str] = []

    p95_limit = 1500 if profile in {"peak", "spike"} else 800
    non2xx_limit = 0.03 if profile in {"peak", "spike"} else 0.01

    http_req_duration = _pick_metric(dispatch_summary, "http_req_duration", {})
    http_req_failed = _pick_metric(dispatch_summary, "http_req_failed", {})

    p95 = http_req_duration.get("p(95)")
    if p95 is None or p95 > p95_limit:
        issues.append(f"Dispatch p95 latency {p95}ms exceeded limit {p95_limit}ms")

    failed_rate = http_req_failed.get("rate")
    if failed_rate is None or failed_rate > non2xx_limit:
        issues.append(f"HTTP non-2xx rate {failed_rate} exceeded limit {non2xx_limit}")

    if ws_summary is None:
        issues.append("WS_HARNESS_FAILED: no summary produced")
        return (False, issues)

    ws_connect_success_rate = ws_summary.get("wsConnectSuccessRate", 0)
    if ws_connect_success_rate < 0.99:
        issues.append(f"WS connect success rate {ws_connect_success_rate:.4f} below 0.99")

    delivery_success_rate = ws_summary.get("deliverySuccessRate", 0)
    if delivery_success_rate < 0.99:
        issues.append(f"WS delivery success rate {delivery_success_rate:.4f} below 0.99")

    return (len(issues) == 0), issues


def _top_fixes(issues: list[str]) -> list[str]:
    fixes: list[str] = []
    issue_text = " ".join(issues).lower()

    fix_rules = [
        (
            "latency" in issue_text,
            "Scale API workers and tune DB pool size; validate dispatch query/index plans under load.",
        ),
        (
            "non-2xx" in issue_text or "http" in issue_text,
            "Audit 4xx/5xx mix by endpoint and status code; separate auth warmup from hot path and raise dispatch quotas only for load environments.",
        ),
        (
            "connect" in issue_text or "delivery" in issue_text,
            "Increase WebSocket worker capacity and tighten connection churn handling; profile broadcast loop and stale-connection cleanup.",
        ),
    ]

    for should_add, fix_text in fix_rules:
        if should_add:
            fixes.append(fix_text)

    while len(fixes) < 3:
        fixes.append("Capture per-endpoint traces and DB wait events during peak windows, then tune the top two bottlenecks before rerun.")

    return fixes[:3]


def build_report(profile: str, dispatch_path: Path, ws_path: Path, out_path: Path) -> None:
    dispatch_summary = _read_json(dispatch_path)
    ws_summary = _read_json(ws_path) if ws_path.exists() else None

    passed, issues = _check_thresholds(profile, dispatch_summary, ws_summary)
    fixes = _top_fixes(issues)

    dispatch_values = _pick_metric(dispatch_summary, "http_req_duration", {})
    failed_values = _pick_metric(dispatch_summary, "http_req_failed", {})

    lines: list[str] = []
    lines.append("# Load Test Go/No-Go Report")
    lines.append("")
    lines.append(f"- Profile: {profile}")
    lines.append(f"- Verdict: {'GO' if passed else 'NO-GO'}")
    lines.append("")
    lines.append("## Dispatch Metrics")
    lines.append("")
    lines.append(f"- p50: {dispatch_values.get('p(50)')} ms")
    lines.append(f"- p95: {dispatch_values.get('p(95)')} ms")
    lines.append(f"- p99: {dispatch_values.get('p(99)')} ms")
    lines.append(f"- HTTP failed rate: {failed_values.get('rate')}")
    lines.append("")
    lines.append("## WebSocket Metrics")
    lines.append("")
    if ws_summary is None:
        lines.append("- WS_HARNESS_FAILED: no summary produced")
    else:
        lines.append(f"- Connect success rate: {ws_summary.get('wsConnectSuccessRate')}")
        lines.append(f"- Delivery success rate: {ws_summary.get('deliverySuccessRate')}")
        lines.append(f"- Reconnects: {ws_summary.get('wsReconnects')}")
        lines.append(f"- Fanout p95 delay: {ws_summary.get('fanoutDelayMs', {}).get('p95')} ms")
        lines.append(f"- Out-of-order frames: {ws_summary.get('outOfOrder')}")
        lines.append(f"- Dropped frames: {ws_summary.get('fanoutDropped')}")
    lines.append("")

    if issues:
        lines.append("## Threshold Failures")
        lines.append("")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")

    lines.append("## Top 3 Fixes")
    lines.append("")
    for fix in fixes:
        lines.append(f"- {fix}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build load-test go/no-go markdown report")
    parser.add_argument("--profile", required=True, choices=["baseline", "peak", "spike", "soak"])
    parser.add_argument("--dispatch-summary", required=True, type=Path)
    parser.add_argument("--ws-summary", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    build_report(args.profile, args.dispatch_summary, args.ws_summary, args.out)


if __name__ == "__main__":
    main()
