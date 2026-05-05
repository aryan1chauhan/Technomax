"""Seeded synthetic scenario generator wired for real dispatch execution."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from simulation.scenario_library import ScenarioDefinition, get_scenario


@dataclass(frozen=True)
class SimulationCase:
    case_id: str
    scenario_name: str
    scenario_tag: str
    priority_type: str
    expected_behavior: str
    condition_type: str
    severity_score: int
    vitals: dict[str, float]
    ambulance_equipment: list[str]
    required_equipment: list[str]
    hospitals: list[dict[str, Any]]

    def to_dispatch_kwargs(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "hospitals": self.hospitals,
            "ambulance_lat": 30.3165,
            "ambulance_lng": 78.0322,
            "condition_type": self.condition_type,
            "severity_score": self.severity_score,
            "vitals": self.vitals,
            "ambulance_equipment": self.ambulance_equipment,
            "required_equipment": self.required_equipment,
            "scenario_context": {
                "scenario_name": self.scenario_name,
                "priority_type": self.priority_type,
                "expected_behavior": self.expected_behavior,
            },
        }


class ScenarioGenerator:
    def __init__(self, seed: int = 42) -> None:
        self.seed = int(seed)

    def generate_cases(self, scenario_name: str, count: int) -> list[SimulationCase]:
        scenario = get_scenario(scenario_name)
        base_seed = _stable_seed(self.seed, scenario_name)
        return [self._build_case(scenario, index, base_seed + index) for index in range(max(0, int(count)))]

    def _build_case(self, scenario: ScenarioDefinition, index: int, case_seed: int) -> SimulationCase:
        rng = random.Random(case_seed)
        severity = max(0.0, min(1.0, scenario.base_severity + rng.uniform(-scenario.severity_noise, scenario.severity_noise)))
        severity_score = int(round(severity * 100.0))

        spo2 = _bounded(scenario.base_vitals["spo2"] + rng.uniform(-6.0, 3.0), 60.0, 99.0)
        heart_rate = _bounded(scenario.base_vitals["heart_rate"] + rng.uniform(-18.0, 20.0), 35.0, 180.0)
        systolic = _bounded(scenario.base_vitals["systolic_bp"] + rng.uniform(-20.0, 18.0), 55.0, 210.0)

        hospitals = _build_hospitals_for_scenario(scenario, rng)
        case_id = f"sim-{scenario.name}-{self.seed}-{index:04d}"
        return SimulationCase(
            case_id=case_id,
            scenario_name=scenario.name,
            scenario_tag=f"{scenario.name}:{scenario.priority_type}",
            priority_type=scenario.priority_type,
            expected_behavior=scenario.expected_behavior,
            condition_type=scenario.condition_type,
            severity_score=severity_score,
            vitals={
                "spo2": round(spo2, 2),
                "pulse": round(heart_rate, 2),
                "heart_rate": round(heart_rate, 2),
                "systolic": round(systolic, 2),
                "systolic_bp": round(systolic, 2),
            },
            ambulance_equipment=list(scenario.ambulance_equipment),
            required_equipment=list(scenario.required_equipment),
            hospitals=hospitals,
        )


def _stable_seed(seed: int, scenario_name: str) -> int:
    digest = hashlib.sha256(f"{seed}:{scenario_name}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _build_hospitals_for_scenario(scenario: ScenarioDefinition, rng: random.Random) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    templates = [
        {
            "id": 101,
            "name": "Cardiac Hub",
            "latitude": 30.3300,
            "longitude": 78.0450,
            "hospital_type": "tertiary",
            "tags": {"cardiac", "stabilization", "critical_care"},
            "equipment": ["defibrillator", "cath_lab", "icu", "oxygen", "ventilator"],
            "total_beds": 24,
            "icu_beds": 7,
        },
        {
            "id": 102,
            "name": "Stroke Center",
            "latitude": 30.3240,
            "longitude": 78.0210,
            "hospital_type": "tertiary",
            "tags": {"stroke", "neuro", "critical_care"},
            "equipment": ["ct_scan", "stroke_unit", "neurology", "oxygen", "ventilator"],
            "total_beds": 18,
            "icu_beds": 5,
        },
        {
            "id": 103,
            "name": "Trauma Hub",
            "latitude": 30.3410,
            "longitude": 78.0610,
            "hospital_type": "tertiary",
            "tags": {"trauma", "stabilization", "critical_care"},
            "equipment": ["surgery", "blood_bank", "trauma_center", "icu", "oxygen", "ventilator"],
            "total_beds": 30,
            "icu_beds": 8,
        },
        {
            "id": 104,
            "name": "Respiratory Care Unit",
            "latitude": 30.3120,
            "longitude": 78.0100,
            "hospital_type": "secondary",
            "tags": {"respiratory", "critical_care"},
            "equipment": ["ventilator", "oxygen", "icu", "basic_monitoring"],
            "total_beds": 20,
            "icu_beds": 4,
        },
        {
            "id": 105,
            "name": "General Secondary",
            "latitude": 30.3060,
            "longitude": 78.0410,
            "hospital_type": "secondary",
            "tags": {"stabilization"},
            "equipment": ["oxygen", "defibrillator", "basic_monitoring"],
            "total_beds": 28,
            "icu_beds": 2,
        },
        {
            "id": 106,
            "name": "Rural Clinic",
            "latitude": 30.2890,
            "longitude": 78.0030,
            "hospital_type": "primary",
            "tags": {"stabilization"},
            "equipment": ["oxygen", "basic_monitoring"],
            "total_beds": 10,
            "icu_beds": 0,
        },
    ]

    hospitals: list[dict[str, Any]] = []
    for template in templates:
        equipment = list(template["equipment"])

        if scenario.name == "mixed_chaos" and rng.random() < 0.35 and len(equipment) > 2:
            equipment.pop(rng.randrange(0, len(equipment)))
        elif scenario.expected_hospital_tags and not (template["tags"] & set(scenario.expected_hospital_tags)):
            if rng.random() < 0.2 and equipment:
                equipment.pop(rng.randrange(0, len(equipment)))

        accepting = rng.random() > (0.22 if scenario.name == "mixed_chaos" else 0.08)
        load_floor = 0.35 if template["tags"] & set(scenario.expected_hospital_tags) else 0.45
        hospital_load = _bounded(rng.uniform(load_floor, 0.96), 0.1, 0.99)

        total_beds = int(template["total_beds"])
        pressure = 1.0 - hospital_load
        available_beds = max(0, min(total_beds, int(round(total_beds * pressure))))

        if scenario.name == "respiratory_failure" and "respiratory" in template["tags"]:
            available_beds = max(1, available_beds)
        if scenario.name == "trauma_stabilization" and "trauma" in template["tags"]:
            available_beds = max(1, available_beds)

        hospitals.append(
            {
                "id": int(template["id"]),
                "name": str(template["name"]),
                "address": "",
                "latitude": float(template["latitude"]),
                "longitude": float(template["longitude"]),
                "available_beds": int(available_beds),
                "icu_beds": int(template["icu_beds"]),
                "equipment": sorted({str(item).strip().lower() for item in equipment if item}),
                "accepting": bool(accepting),
                "specialists": {},
                "specialist_count": 0,
                "data_source": "simulation",
                "last_updated": now,
                "hospital_type": str(template["hospital_type"]),
                "has_icu": bool(int(template["icu_beds"]) > 0),
                "hospital_load": round(float(hospital_load), 4), 
                "total_beds": int(total_beds),
                "score": 0.0,
                "score_breakdown": {},
                "scenario_tags": sorted(template["tags"]),
            }
        )

    rng.shuffle(hospitals)
    return hospitals
