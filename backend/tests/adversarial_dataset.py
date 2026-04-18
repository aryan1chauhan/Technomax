"""Adversarial dataset generator for robustness testing."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from tests.validation_harness import CaseInput


CONDITIONS = ["cardiac_arrest", "stroke", "trauma", "respiratory_distress"]
EQUIPMENT_POOL = ["ventilator", "defibrillator", "icu", "trauma", "oxygen", "ct_scan"]


@dataclass
class AdversarialCase:
    case_input: CaseInput
    scenario: str
    notes: str


def _base_hospitals() -> list[dict[str, Any]]:
    return [
        {
            "hospital_id": "adv_hosp_1",
            "hospital_type": "both",
            "available_beds": 6,
            "total_beds": 20,
            "icu_beds": 3,
            "has_icu": True,
            "equipment": ["oxygen", "defibrillator", "ventilator"],
            "latitude": 30.321,
            "longitude": 78.029,
            "hospital_load": 0.40,
            "accepting": True,
        },
        {
            "hospital_id": "adv_hosp_2",
            "hospital_type": "both",
            "available_beds": 5,
            "total_beds": 24,
            "icu_beds": 2,
            "has_icu": True,
            "equipment": ["oxygen", "ct_scan", "trauma_center"],
            "latitude": 30.308,
            "longitude": 78.040,
            "hospital_load": 0.50,
            "accepting": True,
        },
        {
            "hospital_id": "adv_hosp_3",
            "hospital_type": "both",
            "available_beds": 4,
            "total_beds": 16,
            "icu_beds": 1,
            "has_icu": True,
            "equipment": ["oxygen", "basic_monitoring"],
            "latitude": 30.330,
            "longitude": 78.015,
            "hospital_load": 0.60,
            "accepting": True,
        },
    ]


def _random_required(condition: str) -> list[str]:
    if condition == "cardiac_arrest":
        return ["defibrillator", "oxygen"]
    if condition == "stroke":
        return ["ct_scan", "oxygen"]
    if condition == "trauma":
        return ["trauma", "oxygen"]
    if condition == "respiratory_distress":
        return ["ventilator", "oxygen"]
    return random.sample(EQUIPMENT_POOL, k=2)


def _stable_vitals() -> dict[str, Any]:
    return {
        "bp": "120/80",
        "pulse": 82,
        "oxygen": 97,
    }


def _critical_vitals() -> dict[str, Any]:
    return {
        "bp": "85/50",
        "pulse": 132,
        "oxygen": 78,
    }


def _inject_incorrect_labels(hospitals: list[dict[str, Any]]) -> None:
    bad_labels = {
        "oxygen": "oxyg3n",
        "defibrillator": "defib#",
        "ventilator": "vent!lator",
        "ct_scan": "ct-scn",
        "trauma_center": "traum@",
    }
    for hospital in hospitals:
        hospital["equipment"] = [bad_labels.get(item, item) for item in hospital["equipment"]]


def _inject_stale_load(hospitals: list[dict[str, Any]]) -> None:
    stale_time = datetime.now(timezone.utc) - timedelta(hours=8)
    for idx, hospital in enumerate(hospitals):
        # Deliberately stale / invalid ranges to test resilience.
        hospital["hospital_load"] = 1.4 if idx % 2 == 0 else -0.3
        hospital["last_updated"] = stale_time.isoformat()


def _inject_gps_corruption(hospitals: list[dict[str, Any]]) -> None:
    for idx, hospital in enumerate(hospitals):
        if idx % 2 == 0:
            # Large random offset.
            hospital["latitude"] += random.uniform(-0.35, 0.35)
            hospital["longitude"] += random.uniform(-0.35, 0.35)
        else:
            # Swap lat/lng corruption.
            hospital["latitude"], hospital["longitude"] = hospital["longitude"], hospital["latitude"]


def _inject_no_equipment_match(hospitals: list[dict[str, Any]]) -> None:
    for hospital in hospitals:
        hospital["equipment"] = ["basic_monitoring", "xray"]


def _inject_all_overloaded(hospitals: list[dict[str, Any]]) -> None:
    for hospital in hospitals:
        hospital["available_beds"] = 1
        hospital["total_beds"] = 100
        hospital["hospital_load"] = 0.99


def generate_adversarial_case(index: int) -> AdversarialCase:
    scenario_idx = index % 6
    condition = random.choice(CONDITIONS)
    hospitals = _base_hospitals()

    severity = random.uniform(4.0, 9.5)
    vitals = {
        "bp": f"{int(random.uniform(95, 135))}/{int(random.uniform(60, 90))}",
        "pulse": int(random.uniform(70, 120)),
        "oxygen": int(random.uniform(88, 99)),
    }

    scenario = ""
    notes = ""

    if scenario_idx == 0:
        scenario = "missing_all_vitals"
        vitals = {}
        severity = random.uniform(5.0, 8.5)
        notes = "All vitals removed"
    elif scenario_idx == 1:
        scenario = "contradictory_high_severity_stable_vitals"
        severity = random.uniform(8.5, 10.0)
        vitals = _stable_vitals()
        notes = "High severity with stable vitals"
    elif scenario_idx == 2:
        scenario = "contradictory_low_severity_critical_oxygen"
        severity = random.uniform(1.0, 3.0)
        vitals = _critical_vitals()
        notes = "Low severity with critical oxygen"
    elif scenario_idx == 3:
        scenario = "corrupted_hospital_data"
        _inject_incorrect_labels(hospitals)
        _inject_stale_load(hospitals)
        notes = "Equipment labels corrupted + stale load"
    elif scenario_idx == 4:
        scenario = "gps_corruption"
        _inject_gps_corruption(hospitals)
        notes = "Coordinate offsets and lat/lng swaps"
    else:
        scenario = "extreme_no_match_and_overload"
        _inject_no_equipment_match(hospitals)
        _inject_all_overloaded(hospitals)
        notes = "No required equipment anywhere + overloaded network"

    case = CaseInput(
        case_id=f"ADV-{index:04d}-{scenario}",
        ambulance_equipment=["oxygen"],
        condition=condition,
        severity_score=severity,
        patient_vitals=vitals,
        required_equipment=_random_required(condition),
        hospitals=hospitals,
    )

    return AdversarialCase(case_input=case, scenario=scenario, notes=notes)


def generate_adversarial_dataset(n: int = 500, seed: int = 2026) -> list[AdversarialCase]:
    random.seed(seed)
    n = max(500, int(n))
    return [generate_adversarial_case(i + 1) for i in range(n)]
