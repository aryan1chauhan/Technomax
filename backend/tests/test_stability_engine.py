from app.engine.stability_engine import (
    calculate_equipment_risk,
    calculate_vitals_risk,
    evaluate_stability,
    estimate_survival_time,
)


def test_evaluate_stability_output_shape_and_ranges():
    result = evaluate_stability(
        case_data={
            "severity_score": 6,
            "condition_type": "stroke",
            "vitals": {"bp": "118/76", "pulse": 92, "oxygen": 96},
        },
        ambulance_data={
            "has_oxygen": True,
            "has_ventilator": True,
            "has_defibrillator": True,
        },
        eta_to_best_hospital=22,
    )

    assert set(result.keys()) == {
        "stability_score",
        "estimated_survival_time",
        "stabilization_required",
    }
    assert 0.0 <= result["stability_score"] <= 1.0
    assert result["estimated_survival_time"] >= 1.0
    assert isinstance(result["stabilization_required"], bool)


def test_high_severity_reduces_survival_time():
    low = evaluate_stability(
        case_data={"severity_score": 3, "condition_type": "trauma", "vitals": {}},
        ambulance_data={"has_oxygen": True, "has_ventilator": True, "has_defibrillator": True},
        eta_to_best_hospital=15,
    )
    high = evaluate_stability(
        case_data={"severity_score": 9, "condition_type": "trauma", "vitals": {}},
        ambulance_data={"has_oxygen": True, "has_ventilator": True, "has_defibrillator": True},
        eta_to_best_hospital=15,
    )

    assert high["estimated_survival_time"] < low["estimated_survival_time"]


def test_missing_equipment_reduces_survival_time():
    full = evaluate_stability(
        case_data={"severity_score": 8, "condition_type": "cardiac", "vitals": {}},
        ambulance_data={"has_oxygen": True, "has_ventilator": True, "has_defibrillator": True},
        eta_to_best_hospital=12,
    )
    missing = evaluate_stability(
        case_data={"severity_score": 8, "condition_type": "cardiac", "vitals": {}},
        ambulance_data={"has_oxygen": False, "has_ventilator": True, "has_defibrillator": False},
        eta_to_best_hospital=12,
    )

    assert missing["estimated_survival_time"] < full["estimated_survival_time"]


def test_stabilization_required_when_eta_exceeds_survival_time():
    result = evaluate_stability(
        case_data={
            "severity_score": 10,
            "condition_type": "cardiac_arrest",
            "vitals": {"bp": "70/40", "pulse": 160, "oxygen": 82},
        },
        ambulance_data={"has_oxygen": False, "has_ventilator": False, "has_defibrillator": False},
        eta_to_best_hospital=35,
    )

    assert result["stabilization_required"] is True


def test_missing_vitals_is_handled_safely():
    result = evaluate_stability(
        case_data={"severity_score": 5, "condition_type": "general"},
        ambulance_data={"has_oxygen": True, "has_ventilator": False, "has_defibrillator": True},
        eta_to_best_hospital=10,
    )

    assert isinstance(result["stability_score"], float)
    assert result["estimated_survival_time"] >= 1.0


def test_pure_functions_are_deterministic():
    v1 = calculate_vitals_risk({"bp": "85/60", "pulse": 145, "oxygen": 89})
    v2 = calculate_vitals_risk({"bp": "85/60", "pulse": 145, "oxygen": 89})
    assert v1 == v2

    e1 = calculate_equipment_risk("respiratory", {"has_oxygen": False, "has_ventilator": False})
    e2 = calculate_equipment_risk("respiratory", {"has_oxygen": False, "has_ventilator": False})
    assert e1 == e2

    s1 = estimate_survival_time(8, "respiratory", 0.65, 0.35)
    s2 = estimate_survival_time(8, "respiratory", 0.65, 0.35)
    assert s1 == s2
