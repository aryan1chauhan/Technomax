"""Synthetic chaos dataset generator (1000+ cases)."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


CONDITIONS = ["cardiac", "stroke", "trauma", "respiratory"]
EQUIPMENT = ["ventilator", "defibrillator", "icu", "trauma", "oxygen"]


@dataclass
class ChaosCase:
    case_id: str
    condition: str
    severity: float
    vitals: dict[str, Any]
    required_equipment: list[str]
    stable_hint: bool
    max_safe_eta: float


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _gauss(mean: float, std: float) -> float:
    return random.gauss(mean, std)


def generate_case(case_index: int) -> ChaosCase:
    condition = random.choice(CONDITIONS)

    base_severity = _clip(_gauss(6.0, 2.0), 1.0, 10.0)

    vitals = {
        "bp": _gauss(110.0, 30.0),
        "pulse": _gauss(90.0, 30.0),
        "oxygen": _gauss(95.0, 10.0),
    }

    # Chaos injection: missing vitals
    if random.random() < 0.30:
        vitals[random.choice(list(vitals.keys()))] = None

    # Chaos injection: conflicting severity signal
    if random.random() < 0.20:
        base_severity += random.choice([-3.0, 3.0])
        base_severity = _clip(base_severity, 1.0, 10.0)

    # Chaos injection: critical oxygen drop
    if random.random() < 0.20:
        vitals["oxygen"] = _gauss(70.0, 5.0)

    required_equipment = random.sample(EQUIPMENT, k=random.randint(1, 3))

    # Basic stability hint for penalties (rough heuristic)
    stable_hint = base_severity <= 4.0 and (vitals.get("oxygen") or 100) >= 92
    max_safe_eta = 25.0 if stable_hint else 15.0

    return ChaosCase(
        case_id=f"CHAOS-{case_index:04d}",
        condition=condition,
        severity=base_severity,
        vitals=vitals,
        required_equipment=required_equipment,
        stable_hint=stable_hint,
        max_safe_eta=max_safe_eta,
    )


def generate_dataset(n: int = 1000) -> list[ChaosCase]:
    return [generate_case(i + 1) for i in range(n)]
