"""Structured simulation scenarios for behavioral validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PriorityType = Literal["time", "specialty", "stabilization", "equipment"]


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    priority_type: PriorityType
    expected_behavior: str
    failure_modes: tuple[str, ...]
    condition_type: str
    base_severity: float
    severity_noise: float
    base_vitals: dict[str, float]
    required_equipment: tuple[str, ...]
    ambulance_equipment: tuple[str, ...]
    expected_hospital_tags: tuple[str, ...]


_SCENARIOS: dict[str, ScenarioDefinition] = {
    "cardiac_emergency": ScenarioDefinition(
        name="cardiac_emergency",
        priority_type="time",
        expected_behavior="Prioritize low ETA and immediate stabilization readiness.",
        failure_modes=("eta_delay", "stabilization_miss", "fallback_overuse"),
        condition_type="cardiac",
        base_severity=0.92,
        severity_noise=0.06,
        base_vitals={"heart_rate": 132.0, "systolic_bp": 82.0, "spo2": 90.0},
        required_equipment=("defibrillator", "oxygen"),
        ambulance_equipment=("oxygen",),
        expected_hospital_tags=("cardiac", "stabilization"),
    ),
    "stroke_specialty": ScenarioDefinition(
        name="stroke_specialty",
        priority_type="specialty",
        expected_behavior="Prefer facilities with stroke and neuro treatment capability.",
        failure_modes=("specialty_mismatch", "late_handover", "fallback_overuse"),
        condition_type="stroke",
        base_severity=0.88,
        severity_noise=0.08,
        base_vitals={"heart_rate": 104.0, "systolic_bp": 178.0, "spo2": 93.0},
        required_equipment=("ct_scan",),
        ambulance_equipment=("oxygen",),
        expected_hospital_tags=("stroke", "neuro"),
    ),
    "trauma_stabilization": ScenarioDefinition(
        name="trauma_stabilization",
        priority_type="stabilization",
        expected_behavior="Stabilize first when unstable, then route to trauma-capable center.",
        failure_modes=("stabilization_skip", "unsafe_direct_transfer", "capacity_deadlock"),
        condition_type="trauma",
        base_severity=0.95,
        severity_noise=0.05,
        base_vitals={"heart_rate": 140.0, "systolic_bp": 76.0, "spo2": 88.0},
        required_equipment=("blood_bank", "icu"),
        ambulance_equipment=("oxygen",),
        expected_hospital_tags=("trauma", "stabilization"),
    ),
    "respiratory_failure": ScenarioDefinition(
        name="respiratory_failure",
        priority_type="equipment",
        expected_behavior="Match equipment-intensive needs with ventilator-ready sites.",
        failure_modes=("equipment_gap", "fallback_overuse", "bed_shortage"),
        condition_type="respiratory",
        base_severity=0.9,
        severity_noise=0.07,
        base_vitals={"heart_rate": 118.0, "systolic_bp": 96.0, "spo2": 82.0},
        required_equipment=("ventilator", "oxygen"),
        ambulance_equipment=("oxygen",),
        expected_hospital_tags=("respiratory", "critical_care"),
    ),
    "mixed_chaos": ScenarioDefinition(
        name="mixed_chaos",
        priority_type="stabilization",
        expected_behavior="Remain safe and deterministic under contradictory constraints.",
        failure_modes=("policy_inconsistency", "fallback_chain", "unsafe_selection"),
        condition_type="mixed",
        base_severity=0.93,
        severity_noise=0.1,
        base_vitals={"heart_rate": 125.0, "systolic_bp": 84.0, "spo2": 86.0},
        required_equipment=("oxygen",),
        ambulance_equipment=("oxygen",),
        expected_hospital_tags=("stabilization",),
    ),
}


def get_scenario_library() -> dict[str, ScenarioDefinition]:
    return dict(_SCENARIOS)


def get_scenario(name: str) -> ScenarioDefinition:
    key = str(name).strip().lower()
    if key not in _SCENARIOS:
        supported = ", ".join(sorted(_SCENARIOS))
        raise ValueError(f"Unknown scenario '{name}'. Supported: {supported}")
    return _SCENARIOS[key]


def list_scenarios() -> list[str]:
    return sorted(_SCENARIOS.keys())
