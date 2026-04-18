"""Lightweight drift checks for worker-side observability."""

from __future__ import annotations

from services.metrics_service import metrics


BASELINE = 0.80
_state = {"last_reported_total": 0}


def check_drift() -> bool:
    """Return True when drift is detected.

    Rule:
    - Ignore until 50 samples.
    - Drift when mean_score < BASELINE * 0.9.
    """
    if metrics.total < 50:
        return False

    mean_score = metrics.mean_score
    threshold = BASELINE * 0.9
    drifted = mean_score < threshold

    if drifted and metrics.total != _state["last_reported_total"]:
        print(
            "DRIFT DETECTED:",
            f"mean_score={mean_score:.4f}",
            f"threshold={threshold:.4f}",
            f"total_cases={metrics.total}",
        )
        _state["last_reported_total"] = metrics.total

    return drifted

