"""In-memory metrics store for observability layer.

Lightweight by design:
- No DB writes.
- No blocking operations.
- Updated from worker path, not API path.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MetricsStore:
    total: int = 0
    total_score: float = 0.0
    failures: dict[str, int] = field(default_factory=dict)

    def record(self, *, score: float, failure_type: str | None) -> None:
        self.total += 1
        self.total_score += float(score)
        if failure_type:
            self.failures[failure_type] = self.failures.get(failure_type, 0) + 1

    @property
    def mean_score(self) -> float:
        if self.total <= 0:
            return 0.0
        return self.total_score / self.total

    def summary(self) -> dict[str, object]:
        return {
            "total_cases": self.total,
            "mean_score": self.mean_score,
            "failures": dict(self.failures),
        }


metrics = MetricsStore()

