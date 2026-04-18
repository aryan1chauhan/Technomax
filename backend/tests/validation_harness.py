"""
Decision Validation Harness
===========================

Audit system behavior under pressure:
- Score collapse detection
- Weight dominance analysis  
- Tie-breaker effectiveness
- Oscillation detection
- Ambulance context validation
"""

import json
import statistics
from typing import Any
from dataclasses import dataclass, asdict
from enum import Enum


class DecisionType(str, Enum):
    DIRECT = "direct"
    STABILIZE_FIRST = "stabilize_first"
    EMERGENCY_OVERRIDE = "emergency_override"
    NO_VIABLE = "no_viable_hospital"


class Priority(str, Enum):
    NEAREST = "nearest"
    BEST_EQUIPPED = "best_equipped"
    BALANCED = "balanced"


@dataclass
class CaseExpectation:
    """Ground truth for a single test case"""
    case_id: str
    condition: str
    severity: float
    expected_decision_type: DecisionType
    expected_priority: Priority
    must_not_choose: list[str]
    description: str
    reason: str


@dataclass
class CaseInput:
    """Raw dispatch request parameters"""
    case_id: str
    ambulance_equipment: list[str]
    condition: str
    severity_score: float
    patient_vitals: dict[str, Any]
    required_equipment: list[str]
    hospitals: list[dict[str, Any]]
    ambulance_lat: float = 40.7128
    ambulance_lng: float = -74.0060


@dataclass
class ValidationResult:
    """Result of running one case through validation"""
    case_id: str
    passed: bool
    decision_type_match: bool
    priority_match: bool
    forbidden_hospital_avoided: bool
    decision_type_actual: str
    primary_destination: str
    score_breakdown: dict[str, float]
    issues: list[str]


class SyntheticCaseGenerator:
    """Generate 30-50 test cases covering all risk categories"""
    
    HOSPITALS = {
        "cardiac_hub": {"beds": 20, "icu_beds": 5, "has_icu": True, "hospital_type": "tertiary", 
                       "equipment": ["defibrillator", "cath_lab", "cardiology", "ventilator"]},
        "stroke_center": {"beds": 15, "icu_beds": 4, "has_icu": True, "hospital_type": "tertiary",
                         "equipment": ["ct_scanner", "neurology", "stroke_unit", "thrombectomy"]},
        "trauma_hub": {"beds": 25, "icu_beds": 8, "has_icu": True, "hospital_type": "tertiary",
                      "equipment": ["trauma_center", "surgery", "blood_bank", "ventilator"]},
        "general_secondary": {"beds": 30, "icu_beds": 3, "has_icu": True, "hospital_type": "secondary",
                             "equipment": ["basic_monitoring", "oxygen", "defibrillator"]},
        "rural_clinic": {"beds": 10, "icu_beds": 0, "has_icu": False, "hospital_type": "primary",
                        "equipment": ["oxygen", "basic_monitoring"]},
    }
    
    @staticmethod
    def generate_critical_unstable_cases() -> list[CaseInput]:
        """10 cases: cardiac arrest, severe stroke, major trauma"""
        cases = []
        
        # CRITICAL-1: Cardiac arrest, nearest is fully equipped
        cases.append(CaseInput(
            case_id="CRITICAL-01-cardiac-nearby-full",
            ambulance_equipment=["defibrillator", "oxygen"],
            condition="cardiac_arrest",
            severity_score=9.5,
            patient_vitals={"spo2": 78, "pulse": 0, "systolic": 60},
            ambulance_lat=40.7128,
            ambulance_lng=-74.0060,
            required_equipment=["defibrillator", "cath_lab"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 3.2, "available_beds": 2, 
                 "hospital_id": "cardiac_hub_main", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 5.1, "available_beds": 5,
                 "hospital_id": "general_sec_1", "eta_minutes": 12},
            ]
        ))
        
        # CRITICAL-2: Severe stroke, time-critical
        cases.append(CaseInput(
            case_id="CRITICAL-02-stroke-severe-time",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=9.2,
            patient_vitals={"spo2": 92, "pulse": 98, "systolic": 165},
            required_equipment=["ct_scanner", "neurology"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 7.5, "available_beds": 1,
                 "hospital_id": "stroke_center_1", "eta_minutes": 18},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.0, "available_beds": 8,
                 "hospital_id": "general_sec_2", "eta_minutes": 5},
            ]
        ))
        
        # CRITICAL-3: Major trauma with bleeding
        cases.append(CaseInput(
            case_id="CRITICAL-03-trauma-major-bleed",
            ambulance_equipment=["ventilator", "oxygen"],
            condition="trauma",
            severity_score=9.8,
            patient_vitals={"spo2": 85, "pulse": 125, "systolic": 85},
            required_equipment=["surgery", "blood_bank", "trauma_center"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["trauma_hub"], "distance_km": 12.0, "available_beds": 3,
                 "hospital_id": "trauma_hub_main", "eta_minutes": 22},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 4.5, "available_beds": 10,
                 "hospital_id": "general_sec_3", "eta_minutes": 10},
            ]
        ))
        
        # CRITICAL-4: Respiratory failure, survival tight
        cases.append(CaseInput(
            case_id="CRITICAL-04-respiratory-acute",
            ambulance_equipment=["ventilator", "oxygen"],
            condition="respiratory",
            severity_score=8.9,
            patient_vitals={"spo2": 72, "pulse": 110, "systolic": 95},
            required_equipment=["ventilator"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 6.0, "available_beds": 4,
                 "hospital_id": "cardiac_hub_vent", "eta_minutes": 14},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 1.5, "available_beds": 2,
                 "hospital_id": "rural_1", "eta_minutes": 3},
            ]
        ))
        
        # CRITICAL-5: Cardiac + stroke borderline (anterior STEMI with neuro signs)
        cases.append(CaseInput(
            case_id="CRITICAL-05-cardiac-stroke-combo",
            ambulance_equipment=["defibrillator", "oxygen"],
            condition="cardiac_arrest",
            severity_score=9.1,
            patient_vitals={"spo2": 89, "pulse": 42, "systolic": 72},
            required_equipment=["cath_lab", "ct_scanner"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 8.0, "available_beds": 1,
                 "hospital_id": "cardiac_hub_cath", "eta_minutes": 16},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 9.5, "available_beds": 2,
                 "hospital_id": "stroke_center_neuro", "eta_minutes": 18},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.0, "available_beds": 6,
                 "hospital_id": "general_sec_4", "eta_minutes": 6},
            ]
        ))
        
        # CRITICAL-6: Trauma unstable, no ideal match
        cases.append(CaseInput(
            case_id="CRITICAL-06-trauma-no-ideal",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=8.7,
            patient_vitals={"spo2": 88, "pulse": 130, "systolic": 92},
            required_equipment=["surgery"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 4.0, "available_beds": 5,
                 "hospital_id": "general_sec_5", "eta_minutes": 9},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 6.5, "available_beds": 2,
                 "hospital_id": "cardiac_hub_surgery", "eta_minutes": 14},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 1.2, "available_beds": 1,
                 "hospital_id": "rural_2", "eta_minutes": 2},
            ]
        ))
        
        # CRITICAL-7: Stroke near death, stabilization essential
        cases.append(CaseInput(
            case_id="CRITICAL-07-stroke-near-death",
            ambulance_equipment=["oxygen", "ventilator"],
            condition="stroke",
            severity_score=9.4,
            patient_vitals={"spo2": 82, "pulse": 58, "systolic": 72},
            required_equipment=["neurology"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.5, "available_beds": 4,
                 "hospital_id": "general_sec_6", "eta_minutes": 5},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 15.0, "available_beds": 3,
                 "hospital_id": "stroke_center_advanced", "eta_minutes": 28},
            ]
        ))
        
        # CRITICAL-8: Cardiac arrest in overloaded system
        cases.append(CaseInput(
            case_id="CRITICAL-08-cardiac-all-busy",
            ambulance_equipment=["defibrillator", "oxygen"],
            condition="cardiac_arrest",
            severity_score=9.6,
            patient_vitals={"spo2": 76, "pulse": 0, "systolic": 55},
            required_equipment=["defibrillator"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 5.0, "available_beds": 0,
                 "hospital_id": "cardiac_hub_full", "eta_minutes": 10},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.5, "available_beds": 1,
                 "hospital_id": "general_sec_7", "eta_minutes": 7},
            ]
        ))
        
        # CRITICAL-9: Respiratory arrest, tight window
        cases.append(CaseInput(
            case_id="CRITICAL-09-respiratory-arrest",
            ambulance_equipment=["ventilator", "oxygen"],
            condition="respiratory",
            severity_score=9.9,
            patient_vitals={"spo2": 65, "pulse": 115, "systolic": 110},
            required_equipment=["ventilator", "oxygen"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 4.0, "available_beds": 2,
                 "hospital_id": "cardiac_hub_resp", "eta_minutes": 9},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 1.0, "available_beds": 1,
                 "hospital_id": "rural_3", "eta_minutes": 2},
            ]
        ))
        
        # CRITICAL-10: Trauma massive, one option viable
        cases.append(CaseInput(
            case_id="CRITICAL-10-trauma-massive",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=9.9,
            patient_vitals={"spo2": 80, "pulse": 140, "systolic": 75},
            required_equipment=["surgery", "blood_bank"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["trauma_hub"], "distance_km": 10.0, "available_beds": 2,
                 "hospital_id": "trauma_hub_surg", "eta_minutes": 19},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 2.0, "available_beds": 3,
                 "hospital_id": "rural_4", "eta_minutes": 4},
            ]
        ))
        
        return cases
    
    @staticmethod
    def generate_borderline_cases() -> list[CaseInput]:
        """10 cases: survival ≈ ETA, mixed capabilities"""
        cases = []
        
        # BORDERLINE-1: ETA equals survival exactly
        cases.append(CaseInput(
            case_id="BORDERLINE-01-survival-eq-eta",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=6.5,
            patient_vitals={"spo2": 92, "pulse": 85, "systolic": 105},
            required_equipment=["defibrillator"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 8.0, "available_beds": 3,
                 "hospital_id": "cardiac_hub_test", "eta_minutes": 15},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 4.0, "available_beds": 5,
                 "hospital_id": "general_sec_8", "eta_minutes": 8},
            ]
        ))
        
        # BORDERLINE-2: 0.5 min margin (survival barely ahead)
        cases.append(CaseInput(
            case_id="BORDERLINE-02-tight-margin-survival",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=6.2,
            patient_vitals={"spo2": 94, "pulse": 92, "systolic": 120},
            required_equipment=["ct_scanner"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 6.5, "available_beds": 2,
                 "hospital_id": "stroke_center_tight", "eta_minutes": 14},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.0, "available_beds": 6,
                 "hospital_id": "general_sec_9", "eta_minutes": 6},
            ]
        ))
        
        # BORDERLINE-3: ETA slightly exceeds survival (but stable enough)
        cases.append(CaseInput(
            case_id="BORDERLINE-03-survival-slightly-tight",
            ambulance_equipment=["oxygen", "defibrillator"],
            condition="cardiac_arrest",
            severity_score=5.8,
            patient_vitals={"spo2": 95, "pulse": 88, "systolic": 115},
            required_equipment=["cath_lab"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 7.0, "available_beds": 4,
                 "hospital_id": "cardiac_hub_margin", "eta_minutes": 17},
            ]
        ))
        
        # BORDERLINE-4: Mixed capabilities (cardiac hasn't neuro, neuro hasn't cardiac)
        cases.append(CaseInput(
            case_id="BORDERLINE-04-mixed-capability",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=5.5,
            patient_vitals={"spo2": 93, "pulse": 95, "systolic": 125},
            required_equipment=["neurology"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 4.0, "available_beds": 3,
                 "hospital_id": "cardiac_hub_no_neuro", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 9.0, "available_beds": 2,
                 "hospital_id": "stroke_center_far", "eta_minutes": 16},
            ]
        ))
        
        # BORDERLINE-5: Two equally viable options
        cases.append(CaseInput(
            case_id="BORDERLINE-05-tied-options",
            ambulance_equipment=["oxygen", "ventilator"],
            condition="respiratory",
            severity_score=5.2,
            patient_vitals={"spo2": 90, "pulse": 100, "systolic": 118},
            required_equipment=["ventilator"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 5.0, "available_beds": 2,
                 "hospital_id": "cardiac_hub_resp_eq", "eta_minutes": 10},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 5.5, "available_beds": 2,
                 "hospital_id": "stroke_center_resp_eq", "eta_minutes": 11},
            ]
        ))
        
        # BORDERLINE-6: Specialty available but far
        cases.append(CaseInput(
            case_id="BORDERLINE-06-specialty-far",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=5.9,
            patient_vitals={"spo2": 92, "pulse": 0, "systolic": 70},
            required_equipment=["cath_lab"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 15.0, "available_beds": 1,
                 "hospital_id": "cardiac_hub_distant", "eta_minutes": 28},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.5, "available_beds": 3,
                 "hospital_id": "general_sec_10", "eta_minutes": 5},
            ]
        ))
        
        # BORDERLINE-7: High load at all
        cases.append(CaseInput(
            case_id="BORDERLINE-07-all-overloaded",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=5.5,
            patient_vitals={"spo2": 91, "pulse": 98, "systolic": 128},
            required_equipment=["ct_scanner"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 4.0, "available_beds": 1,
                 "hospital_id": "stroke_center_busy", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 5.0, "available_beds": 1,
                 "hospital_id": "general_sec_busy", "eta_minutes": 10},
            ]
        ))
        
        # BORDERLINE-8: Stabilization vs. direct tradeoff
        cases.append(CaseInput(
            case_id="BORDERLINE-08-stabilize-vs-direct",
            ambulance_equipment=["oxygen", "ventilator"],
            condition="stroke",
            severity_score=6.1,
            patient_vitals={"spo2": 88, "pulse": 102, "systolic": 92},
            required_equipment=["neurology"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.0, "available_beds": 4,
                 "hospital_id": "general_sec_stabilize", "eta_minutes": 6},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 12.0, "available_beds": 2,
                 "hospital_id": "stroke_center_advanced_far", "eta_minutes": 22},
            ]
        ))
        
        # BORDERLINE-9: Equipment gaps across all
        cases.append(CaseInput(
            case_id="BORDERLINE-09-equipment-gaps",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=5.7,
            patient_vitals={"spo2": 91, "pulse": 105, "systolic": 104},
            required_equipment=["trauma_center", "blood_bank"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 4.0, "available_beds": 3,
                 "hospital_id": "general_sec_no_trauma", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 6.0, "available_beds": 2,
                 "hospital_id": "cardiac_hub_no_trauma", "eta_minutes": 12},
            ]
        ))
        
        # BORDERLINE-10: Ambulance equipment critical
        cases.append(CaseInput(
            case_id="BORDERLINE-10-ambulance-critical",
            ambulance_equipment=["ventilator", "oxygen", "defibrillator"],
            condition="respiratory",
            severity_score=5.4,
            patient_vitals={"spo2": 87, "pulse": 108, "systolic": 112},
            required_equipment=["ventilator"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 2.0, "available_beds": 2,
                 "hospital_id": "rural_5", "eta_minutes": 4},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 8.0, "available_beds": 1,
                 "hospital_id": "cardiac_hub_backup", "eta_minutes": 16},
            ]
        ))
        
        return cases
    
    @staticmethod
    def generate_stable_cases() -> list[CaseInput]:
        """10 cases: stable/mild, clear optimal choice"""
        cases = []
        
        # STABLE-1: Simple fracture, nearest is fine
        cases.append(CaseInput(
            case_id="STABLE-01-fracture-simple",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=2.5,
            patient_vitals={"spo2": 97, "pulse": 82, "systolic": 130},
            required_equipment=[],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.0, "available_beds": 8,
                 "hospital_id": "general_sec_11", "eta_minutes": 4},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 8.0, "available_beds": 2,
                 "hospital_id": "cardiac_hub_far_stable", "eta_minutes": 16},
            ]
        ))
        
        # STABLE-2: Mild respiratory
        cases.append(CaseInput(
            case_id="STABLE-02-respiratory-mild",
            ambulance_equipment=["oxygen"],
            condition="respiratory",
            severity_score=2.8,
            patient_vitals={"spo2": 94, "pulse": 88, "systolic": 128},
            required_equipment=["oxygen"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.0, "available_beds": 7,
                 "hospital_id": "general_sec_12", "eta_minutes": 6},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 1.5, "available_beds": 3,
                 "hospital_id": "rural_6", "eta_minutes": 3},
            ]
        ))
        
        # STABLE-3: Angina (not acute MI)
        cases.append(CaseInput(
            case_id="STABLE-03-angina-stable",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=3.2,
            patient_vitals={"spo2": 96, "pulse": 78, "systolic": 135},
            required_equipment=["cardiac_monitoring"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 5.0, "available_beds": 5,
                 "hospital_id": "cardiac_hub_stable", "eta_minutes": 10},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 6.0, "available_beds": 6,
                 "hospital_id": "general_sec_13", "eta_minutes": 12},
            ]
        ))
        
        # STABLE-4: TIA (transient stroke)
        cases.append(CaseInput(
            case_id="STABLE-04-tia-transient",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=3.0,
            patient_vitals={"spo2": 95, "pulse": 85, "systolic": 138},
            required_equipment=["ct_scanner"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.5, "available_beds": 5,
                 "hospital_id": "general_sec_14", "eta_minutes": 5},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 8.0, "available_beds": 3,
                 "hospital_id": "stroke_center_tia", "eta_minutes": 15},
            ]
        ))
        
        # STABLE-5: Minor cut/bleeding
        cases.append(CaseInput(
            case_id="STABLE-05-bleeding-minor",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=1.8,
            patient_vitals={"spo2": 98, "pulse": 80, "systolic": 132},
            required_equipment=[],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 1.0, "available_beds": 4,
                 "hospital_id": "rural_7", "eta_minutes": 2},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 4.0, "available_beds": 7,
                 "hospital_id": "general_sec_15", "eta_minutes": 8},
            ]
        ))
        
        # STABLE-6: Cold symptoms
        cases.append(CaseInput(
            case_id="STABLE-06-cold-symptoms",
            ambulance_equipment=["oxygen"],
            condition="respiratory",
            severity_score=1.5,
            patient_vitals={"spo2": 96, "pulse": 75, "systolic": 125},
            required_equipment=[],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.0, "available_beds": 10,
                 "hospital_id": "general_sec_16", "eta_minutes": 4},
            ]
        ))
        
        # STABLE-7: Stable cardiac monitoring
        cases.append(CaseInput(
            case_id="STABLE-07-cardiac-monitoring",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=2.2,
            patient_vitals={"spo2": 96, "pulse": 82, "systolic": 128},
            required_equipment=["cardiac_monitoring"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.5, "available_beds": 6,
                 "hospital_id": "general_sec_17", "eta_minutes": 7},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 7.0, "available_beds": 4,
                 "hospital_id": "cardiac_hub_routine", "eta_minutes": 14},
            ]
        ))
        
        # STABLE-8: Stable burn (not critical)
        cases.append(CaseInput(
            case_id="STABLE-08-burn-light",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=2.5,
            patient_vitals={"spo2": 95, "pulse": 85, "systolic": 130},
            required_equipment=[],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 4.0, "available_beds": 7,
                 "hospital_id": "general_sec_18", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 6.0, "available_beds": 3,
                 "hospital_id": "cardiac_hub_burn", "eta_minutes": 12},
            ]
        ))
        
        # STABLE-9: Stable dehydration
        cases.append(CaseInput(
            case_id="STABLE-09-dehydration",
            ambulance_equipment=["oxygen"],
            condition="respiratory",
            severity_score=2.0,
            patient_vitals={"spo2": 94, "pulse": 92, "systolic": 112},
            required_equipment=[],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.5, "available_beds": 8,
                 "hospital_id": "general_sec_19", "eta_minutes": 5},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 3.0, "available_beds": 2,
                 "hospital_id": "rural_8", "eta_minutes": 6},
            ]
        ))
        
        # STABLE-10: Stable chest pain (likely musculoskeletal)
        cases.append(CaseInput(
            case_id="STABLE-10-chest-pain-msk",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=1.9,
            patient_vitals={"spo2": 97, "pulse": 76, "systolic": 132},
            required_equipment=[],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.0, "available_beds": 9,
                 "hospital_id": "general_sec_20", "eta_minutes": 4},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 5.0, "available_beds": 5,
                 "hospital_id": "cardiac_hub_msk", "eta_minutes": 10},
            ]
        ))
        
        return cases
    
    @staticmethod
    def generate_no_perfect_match_cases() -> list[CaseInput]:
        """10 cases: equipment missing everywhere, force best-effort"""
        cases = []
        
        # NO_MATCH-1: Trauma needs surgery, none available
        cases.append(CaseInput(
            case_id="NO_MATCH-01-trauma-no-surgery",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=6.5,
            patient_vitals={"spo2": 91, "pulse": 110, "systolic": 100},
            required_equipment=["surgery"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.0, "available_beds": 4,
                 "hospital_id": "general_sec_21", "eta_minutes": 6},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 2.0, "available_beds": 2,
                 "hospital_id": "rural_9", "eta_minutes": 4},
            ]
        ))
        
        # NO_MATCH-2: Stroke needs neuro, none available
        cases.append(CaseInput(
            case_id="NO_MATCH-02-stroke-no-neuro",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=7.2,
            patient_vitals={"spo2": 92, "pulse": 100, "systolic": 115},
            required_equipment=["neurology"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 5.0, "available_beds": 3,
                 "hospital_id": "cardiac_hub_no_neuro_2", "eta_minutes": 10},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 3.0, "available_beds": 1,
                 "hospital_id": "rural_10", "eta_minutes": 6},
            ]
        ))
        
        # NO_MATCH-3: Cardiac needs labs, none available
        cases.append(CaseInput(
            case_id="NO_MATCH-03-cardiac-no-cath",
            ambulance_equipment=["defibrillator", "oxygen"],
            condition="cardiac_arrest",
            severity_score=7.8,
            patient_vitals={"spo2": 90, "pulse": 0, "systolic": 65},
            required_equipment=["cath_lab"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.5, "available_beds": 2,
                 "hospital_id": "general_sec_22", "eta_minutes": 5},
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 8.0, "available_beds": 1,
                 "hospital_id": "stroke_center_no_cath", "eta_minutes": 15},
            ]
        ))
        
        # NO_MATCH-4: All hospitals at capacity
        cases.append(CaseInput(
            case_id="NO_MATCH-04-all-full",
            ambulance_equipment=["ventilator", "oxygen"],
            condition="respiratory",
            severity_score=7.0,
            patient_vitals={"spo2": 85, "pulse": 115, "systolic": 108},
            required_equipment=["ventilator"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 4.0, "available_beds": 0,
                 "hospital_id": "cardiac_hub_full_2", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 5.0, "available_beds": 0,
                 "hospital_id": "general_sec_full", "eta_minutes": 10},
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 2.0, "available_beds": 0,
                 "hospital_id": "rural_full", "eta_minutes": 4},
            ]
        ))
        
        # NO_MATCH-5: No hospitals in network (edge case test)
        cases.append(CaseInput(
            case_id="NO_MATCH-05-single-poor-option",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=7.5,
            patient_vitals={"spo2": 88, "pulse": 0, "systolic": 70},
            required_equipment=["cath_lab"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["rural_clinic"], "distance_km": 25.0, "available_beds": 1,
                 "hospital_id": "rural_11_distant", "eta_minutes": 45},
            ]
        ))
        
        # NO_MATCH-6: Specialized equipment everywhere missing
        cases.append(CaseInput(
            case_id="NO_MATCH-06-specialized-gap",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=6.8,
            patient_vitals={"spo2": 91, "pulse": 98, "systolic": 125},
            required_equipment=["thrombectomy"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 3.0, "available_beds": 5,
                 "hospital_id": "general_sec_23", "eta_minutes": 6},
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 6.0, "available_beds": 2,
                 "hospital_id": "cardiac_hub_no_thrombectomy", "eta_minutes": 12},
            ]
        ))
        
        # NO_MATCH-7: Both nearby hospitals below capacity but terrible equipment matches
        cases.append(CaseInput(
            case_id="NO_MATCH-07-weak-equipment-available",
            ambulance_equipment=["oxygen"],
            condition="cardiac_arrest",
            severity_score=6.3,
            patient_vitals={"spo2": 92, "pulse": 0, "systolic": 68},
            required_equipment=["cath_lab", "defibrillator"],
            hospitals=[
                {"beds": 15, "icu_beds": 2, "has_icu": True, "hospital_type": "secondary", 
                 "equipment": ["oxygen", "basic_monitoring"], "distance_km": 2.0, "available_beds": 8,
                 "hospital_id": "basic_hosp_1", "eta_minutes": 4},
                {"beds": 12, "icu_beds": 1, "has_icu": False, "hospital_type": "primary",
                 "equipment": ["oxygen"], "distance_km": 3.5, "available_beds": 6,
                 "hospital_id": "basic_hosp_2", "eta_minutes": 7},
            ]
        ))
        
        # NO_MATCH-8: Distance penalty dominates all
        cases.append(CaseInput(
            case_id="NO_MATCH-08-all-far",
            ambulance_equipment=["oxygen"],
            condition="stroke",
            severity_score=6.5,
            patient_vitals={"spo2": 91, "pulse": 100, "systolic": 120},
            required_equipment=["neurology"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["stroke_center"], "distance_km": 50.0, "available_beds": 2,
                 "hospital_id": "stroke_center_too_far", "eta_minutes": 95},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 40.0, "available_beds": 5,
                 "hospital_id": "general_sec_far", "eta_minutes": 75},
            ]
        ))
        
        # NO_MATCH-9: Conflicting priorities (equipment vs. proximity)
        cases.append(CaseInput(
            case_id="NO_MATCH-09-equipment-vs-proximity",
            ambulance_equipment=["oxygen"],
            condition="trauma",
            severity_score=5.9,
            patient_vitals={"spo2": 90, "pulse": 120, "systolic": 95},
            required_equipment=["trauma_center"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["trauma_hub"], "distance_km": 30.0, "available_beds": 1,
                 "hospital_id": "trauma_hub_far", "eta_minutes": 55},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 2.0, "available_beds": 8,
                 "hospital_id": "general_sec_near_no_trauma", "eta_minutes": 4},
            ]
        ))
        
        # NO_MATCH-10: One hospital has everything but zero beds
        cases.append(CaseInput(
            case_id="NO_MATCH-10-perfect-but-full",
            ambulance_equipment=["defibrillator", "oxygen"],
            condition="cardiac_arrest",
            severity_score=7.4,
            patient_vitals={"spo2": 88, "pulse": 0, "systolic": 62},
            required_equipment=["cath_lab"],
            hospitals=[
                {**SyntheticCaseGenerator.HOSPITALS["cardiac_hub"], "distance_km": 4.0, "available_beds": 0,
                 "hospital_id": "cardiac_hub_perfect_full", "eta_minutes": 8},
                {**SyntheticCaseGenerator.HOSPITALS["general_secondary"], "distance_km": 5.0, "available_beds": 3,
                 "hospital_id": "general_sec_backup_nm", "eta_minutes": 10},
            ]
        ))
        
        return cases
    
    @staticmethod
    def generate_all_cases() -> list[CaseInput]:
        """Generate all 40 test cases"""
        all_cases = (
            SyntheticCaseGenerator.generate_critical_unstable_cases() +
            SyntheticCaseGenerator.generate_borderline_cases() +
            SyntheticCaseGenerator.generate_stable_cases() +
            SyntheticCaseGenerator.generate_no_perfect_match_cases()
        )
        return all_cases


class ExpectationLibrary:
    """Ground truth expectations for each case"""
    
    EXPECTATIONS = {
        # CRITICAL cases
        "CRITICAL-01-cardiac-nearby-full": CaseExpectation(
            case_id="CRITICAL-01-cardiac-nearby-full",
            condition="cardiac_arrest",
            severity=9.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=["general_sec_1"],
            description="Cardiac arrest, nearest is fully equipped cardiac hub",
            reason="Defibrillator critical, cath lab available, close proximity overrides distance"
        ),
        
        "CRITICAL-02-stroke-severe-time": CaseExpectation(
            case_id="CRITICAL-02-stroke-severe-time",
            condition="stroke",
            severity=9.2,
            expected_decision_type=DecisionType.STABILIZE_FIRST,
            expected_priority=Priority.BALANCED,
            must_not_choose=["stroke_center_1"],
            description="Severe stroke with wide eta/survival gap",
            reason="ETA 18 >> survival ~8; stabilize at nearby general first, then re-dispatch to stroke center"
        ),
        
        "CRITICAL-03-trauma-major-bleed": CaseExpectation(
            case_id="CRITICAL-03-trauma-major-bleed",
            condition="trauma",
            severity=9.8,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=["general_sec_3"],
            description="Major trauma, only trauma hub has required equipment",
            reason="Surgery + blood_bank critical; equipment overrides ETA distance"
        ),
        
        "CRITICAL-04-respiratory-acute": CaseExpectation(
            case_id="CRITICAL-04-respiratory-acute",
            condition="respiratory",
            severity=8.9,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=["rural_1"],
            description="Respiratory failure, survival tight with ambulance ventilator support",
            reason="Ambulance +8min survival boost; cardiac_hub has ventilator, rural clinic does not"
        ),
        
        "CRITICAL-05-cardiac-stroke-combo": CaseExpectation(
            case_id="CRITICAL-05-cardiac-stroke-combo",
            condition="cardiac_arrest",
            severity=9.1,
            expected_decision_type=DecisionType.STABILIZE_FIRST,
            expected_priority=Priority.BALANCED,
            must_not_choose=["cardiac_hub_cath", "stroke_center_neuro"],
            description="Cardiac + neuro signs; no single hospital fully optimal",
            reason="General secondary nearby stabilizable; then choose based on improving vitals"
        ),
        
        "CRITICAL-06-trauma-no-ideal": CaseExpectation(
            case_id="CRITICAL-06-trauma-no-ideal",
            condition="trauma",
            severity=8.7,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=["rural_2"],
            description="Trauma with no ideal hospital match",
            reason="General secondary + cardiac hub; choose general for proximity + basic capability"
        ),
        
        "CRITICAL-07-stroke-near-death": CaseExpectation(
            case_id="CRITICAL-07-stroke-near-death",
            condition="stroke",
            severity=9.4,
            expected_decision_type=DecisionType.STABILIZE_FIRST,
            expected_priority=Priority.NEAREST,
            must_not_choose=["stroke_center_advanced"],
            description="Stroke patient near death, stabilization essential",
            reason="Survival window critical; general secondary 5min stabilization mandatory"
        ),
        
        "CRITICAL-08-cardiac-all-busy": CaseExpectation(
            case_id="CRITICAL-08-cardiac-all-busy",
            condition="cardiac_arrest",
            severity=9.6,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=["cardiac_hub_full"],
            description="Cardiac with no ideal beds, emergency override",
            reason="Cardiac hub full; must use general secondary despite suboptimal equipment"
        ),
        
        "CRITICAL-09-respiratory-arrest": CaseExpectation(
            case_id="CRITICAL-09-respiratory-arrest",
            condition="respiratory",
            severity=9.9,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=["rural_3"],
            description="Respiratory arrest, ventilator critical",
            reason="Cardiac hub has ventilator + oxygen; rural clinic minimal capability"
        ),
        
        "CRITICAL-10-trauma-massive": CaseExpectation(
            case_id="CRITICAL-10-trauma-massive",
            condition="trauma",
            severity=9.9,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=["rural_4"],
            description="Massive trauma, only trauma hub viable",
            reason="Surgery + blood_bank essential; rural clinic cannot handle"
        ),

        # BORDERLINE cases (Survival ≈ ETA)
        "BORDERLINE-01-survival-eq-eta": CaseExpectation(
            case_id="BORDERLINE-01-survival-eq-eta",
            condition="cardiac_arrest",
            severity=6.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=[],
            description="ETA equals survivalExactly",
            reason="Cardiac hub has better equipment and is within survival window"
        ),
        "BORDERLINE-02-tight-margin-survival": CaseExpectation(
            case_id="BORDERLINE-02-tight-margin-survival",
            condition="stroke",
            severity=6.2,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=[],
            description="Barely survival ahead of ETA",
            reason="Specialized stroke center is reachable and preferred"
        ),
        "BORDERLINE-03-survival-slightly-tight": CaseExpectation(
            case_id="BORDERLINE-03-survival-slightly-tight",
            condition="cardiac_arrest",
            severity=5.8,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=[],
            description="ETA slightly tight but cardiac hub reachable",
            reason="Mid-severity cardiac case; catholic lab required, ETA 17 well within 35min baseline window."
        ),
        "BORDERLINE-04-mixed-capability": CaseExpectation(
            case_id="BORDERLINE-04-mixed-capability",
            condition="stroke",
            severity=5.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=[],
            description="Neuro center vs cardiac hub",
            reason="Neurology specialty required for stroke even if further"
        ),
        "BORDERLINE-05-tied-options": CaseExpectation(
            case_id="BORDERLINE-05-tied-options",
            condition="respiratory",
            severity=5.2,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Two equally viable hubs",
            reason="Both hospitals have required equipment; ETA difference is negligible"
        ),
        "BORDERLINE-06-specialty-far": CaseExpectation(
            case_id="BORDERLINE-06-specialty-far",
            condition="cardiac_arrest",
            severity=5.9,
            expected_decision_type=DecisionType.STABILIZE_FIRST,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Critical cardiac, specialty center too far",
            reason="Low vitals and high ETA to hub requires immediate stabilization at nearest secondary"
        ),
        "BORDERLINE-07-all-overloaded": CaseExpectation(
            case_id="BORDERLINE-07-all-overloaded",
            condition="stroke",
            severity=5.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="All candidate hospitals busy",
            reason="Choose best match despite load if survival window allows"
        ),
        "BORDERLINE-08-stabilize-vs-direct": CaseExpectation(
            case_id="BORDERLINE-08-stabilize-vs-direct",
            condition="stroke",
            severity=6.1,
            expected_decision_type=DecisionType.STABILIZE_FIRST,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Stabilization vs long direct transit",
            reason="ETA 22min to specialty vs 6min to secondary; stabilization required first"
        ),
        "BORDERLINE-09-equipment-gaps": CaseExpectation(
            case_id="BORDERLINE-09-equipment-gaps",
            condition="trauma",
            severity=5.7,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Incomplete equipment at all candidates",
            reason="Choose secondary for proximity if specialty centers also lack specific trauma gear"
        ),
        "BORDERLINE-10-ambulance-critical": CaseExpectation(
            case_id="BORDERLINE-10-ambulance-critical",
            condition="respiratory",
            severity=5.4,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=[],
            description="Ambulance equipment extends window",
            reason="Ambulance ventilator support allows reaching better-equipped cardiac hub"
        ),

        # STABLE cases (Clear optimal choices)
        "STABLE-01-fracture-simple": CaseExpectation(
            case_id="STABLE-01-fracture-simple",
            condition="trauma",
            severity=2.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Simple fracture",
            reason="Nearest hospital is more than sufficient for minor trauma"
        ),
        "STABLE-02-respiratory-mild": CaseExpectation(
            case_id="STABLE-02-respiratory-mild",
            condition="respiratory",
            severity=2.8,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Mild respiratory distress",
            reason="Rural clinic provides fastest relief for mild symptoms"
        ),
        "STABLE-03-angina-stable": CaseExpectation(
            case_id="STABLE-03-angina-stable",
            condition="cardiac_arrest",
            severity=3.2,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BEST_EQUIPPED,
            must_not_choose=[],
            description="Stable angina",
            reason="Prefer specialized cardiac monitoring for potential complication"
        ),
        "STABLE-04-tia-transient": CaseExpectation(
            case_id="STABLE-04-tia-transient",
            condition="stroke",
            severity=3.0,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="TIA (Transient Ischemic Attack)",
            reason="Fastest proximity for diagnostics is priority for TIA"
        ),
        "STABLE-05-bleeding-minor": CaseExpectation(
            case_id="STABLE-05-bleeding-minor",
            condition="trauma",
            severity=1.8,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Minor bleeding",
            reason="Nearest primary care facility is sufficient"
        ),
        "STABLE-06-cold-symptoms": CaseExpectation(
            case_id="STABLE-06-cold-symptoms",
            condition="respiratory",
            severity=1.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Cold/Flu symptoms",
            reason="Non-emergency case; simple triage to nearest facility"
        ),
        "STABLE-07-cardiac-monitoring": CaseExpectation(
            case_id="STABLE-07-cardiac-monitoring",
            condition="cardiac_arrest",
            severity=2.2,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Stable cardiac monitoring request",
            reason="Nearest secondary hospital has required monitoring equipment"
        ),
        "STABLE-08-burn-light": CaseExpectation(
            case_id="STABLE-08-burn-light",
            condition="trauma",
            severity=2.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Light burn",
            reason="Standard ER treatment at nearest secondary is best"
        ),
        "STABLE-09-dehydration": CaseExpectation(
            case_id="STABLE-09-dehydration",
            condition="respiratory",
            severity=2.0,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Stable dehydration",
            reason="IV fluids available at nearest secondary"
        ),
        "STABLE-10-chest-pain-msk": CaseExpectation(
            case_id="STABLE-10-chest-pain-msk",
            condition="cardiac_arrest",
            severity=1.9,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Likely musculoskeletal chest pain",
            reason="Low severity cardiac triage goes to nearest general hospital"
        ),

        # NO_MATCH cases (Best-effort scenarios)
        "NO_MATCH-01-trauma-no-surgery": CaseExpectation(
            case_id="NO_MATCH-01-trauma-no-surgery",
            condition="trauma",
            severity=6.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Surgery required but unavailable",
            reason="When required equipment is missing everywhere, proximity becomes tie-breaker"
        ),
        "NO_MATCH-02-stroke-no-neuro": CaseExpectation(
            case_id="NO_MATCH-02-stroke-no-neuro",
            condition="stroke",
            severity=7.2,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Neurology needed but missing",
            reason="Route to highest tier available hospital for best-effort triage"
        ),
        "NO_MATCH-03-cardiac-no-cath": CaseExpectation(
            case_id="NO_MATCH-03-cardiac-no-cath",
            condition="cardiac_arrest",
            severity=7.8,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Cath lab needed but missing",
            reason="Proximity for baseline stabilization since specialty care is unavailable"
        ),
        "NO_MATCH-04-all-full": CaseExpectation(
            case_id="NO_MATCH-04-all-full",
            condition="respiratory",
            severity=7.0,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="All Candidate hospitals at zero capacity",
            reason="Emergency capacity override; route to nearest regardless of load"
        ),
        "NO_MATCH-05-single-poor-option": CaseExpectation(
            case_id="NO_MATCH-05-single-poor-option",
            condition="cardiac_arrest",
            severity=7.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Only one very distant option",
            reason="Dispatcher must choose the only available hospital despite distance"
        ),
        "NO_MATCH-06-specialized-gap": CaseExpectation(
            case_id="NO_MATCH-06-specialized-gap",
            condition="stroke",
            severity=6.8,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Rare specialized equipment missing",
            reason="Route to cardiac hub as best effort for high-level monitoring"
        ),
        "NO_MATCH-07-weak-equipment-available": CaseExpectation(
            case_id="NO_MATCH-07-weak-equipment-available",
            condition="cardiac_arrest",
            severity=6.3,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Critical needs, poor matching hospitals",
            reason="Baseline care at nearest facility is better than nothing"
        ),
        "NO_MATCH-08-all-far": CaseExpectation(
            case_id="NO_MATCH-08-all-far",
            condition="stroke",
            severity=6.5,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="All hospitals are very far",
            reason="Patient survival depends on fastest possible handoff"
        ),
        "NO_MATCH-09-equipment-vs-proximity": CaseExpectation(
            case_id="NO_MATCH-09-equipment-vs-proximity",
            condition="trauma",
            severity=5.9,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.NEAREST,
            must_not_choose=[],
            description="Trauma hub (far) vs General (near)",
            reason="High distance penalty for trauma hub makes general secondary the safer choice"
        ),
        "NO_MATCH-10-perfect-but-full": CaseExpectation(
            case_id="NO_MATCH-10-perfect-but-full",
            condition="cardiac_arrest",
            severity=7.4,
            expected_decision_type=DecisionType.DIRECT,
            expected_priority=Priority.BALANCED,
            must_not_choose=[],
            description="Optimal hub is full",
            reason="Route to secondary backup to ensure bed availability"
        ),

    }
    
    @staticmethod
    def get_expectation(case_id: str) -> CaseExpectation:
        """Get expectation for a case, or return None if not defined"""
        return ExpectationLibrary.EXPECTATIONS.get(case_id)
    
    @staticmethod
    def add_expectation(case_id: str, expectation: CaseExpectation):
        """Add/update an expectation"""
        ExpectationLibrary.EXPECTATIONS[case_id] = expectation


class DistributionAnalyzer:
    """Track score component distributions to detect weight dominance"""
    
    def __init__(self):
        self.s_survival_scores = []
        self.s_treatment_scores = []
        self.s_equipment_scores = []
        self.s_eta_scores = []
        self.s_load_scores = []
        self.final_scores = []
    
    def record(self, breakdown: dict):
        """Record a score breakdown"""
        self.s_survival_scores.append(breakdown.get("S_survival", 0.0))
        self.s_treatment_scores.append(breakdown.get("S_treatment", 0.0))
        self.s_equipment_scores.append(breakdown.get("S_equipment", 0.0))
        self.s_eta_scores.append(breakdown.get("S_eta", 0.0))
        self.s_load_scores.append(breakdown.get("S_load", 0.0))
        self.final_scores.append(breakdown.get("final_score", 0.0))
    
    def report(self) -> dict:
        """Generate distribution report"""
        if not self.final_scores:
            return {}
        
        report = {
            "S_survival": {
                "mean": statistics.mean(self.s_survival_scores),
                "stdev": statistics.stdev(self.s_survival_scores) if len(self.s_survival_scores) > 1 else 0,
                "min": min(self.s_survival_scores),
                "max": max(self.s_survival_scores),
            },
            "S_treatment": {
                "mean": statistics.mean(self.s_treatment_scores),
                "stdev": statistics.stdev(self.s_treatment_scores) if len(self.s_treatment_scores) > 1 else 0,
                "min": min(self.s_treatment_scores),
                "max": max(self.s_treatment_scores),
            },
            "S_equipment": {
                "mean": statistics.mean(self.s_equipment_scores),
                "stdev": statistics.stdev(self.s_equipment_scores) if len(self.s_equipment_scores) > 1 else 0,
                "min": min(self.s_equipment_scores),
                "max": max(self.s_equipment_scores),
            },
            "S_eta": {
                "mean": statistics.mean(self.s_eta_scores),
                "stdev": statistics.stdev(self.s_eta_scores) if len(self.s_eta_scores) > 1 else 0,
                "min": min(self.s_eta_scores),
                "max": max(self.s_eta_scores),
            },
            "S_load": {
                "mean": statistics.mean(self.s_load_scores),
                "stdev": statistics.stdev(self.s_load_scores) if len(self.s_load_scores) > 1 else 0,
                "min": min(self.s_load_scores),
                "max": max(self.s_load_scores),
            },
            "final_score": {
                "mean": statistics.mean(self.final_scores),
                "stdev": statistics.stdev(self.final_scores) if len(self.final_scores) > 1 else 0,
                "min": min(self.final_scores),
                "max": max(self.final_scores),
            }
        }
        
        return report
    
    def detect_dominance(self, threshold: float = 0.15) -> dict:
        """Detect if one component dominates all others"""
        report = self.report()
        if not report:
            return {}
            
        dominance = {}
        
        for component in ["S_survival", "S_treatment", "S_equipment", "S_eta", "S_load"]:
            if component not in report:
                continue
            if report[component]["stdev"] > 0:
                score = report[component]["mean"]
                others_mean = statistics.mean([
                    report[c]["mean"] for c in ["S_survival", "S_treatment", "S_equipment", "S_eta", "S_load"]
                    if c != component
                ])
                gap = abs(score - others_mean)
                dominance[component] = {"gap": gap, "dominates": gap > threshold}
        
        return dominance


class OscillationDetector:
    """Detect if same input produces different outputs"""
    
    def __init__(self):
        self.request_cache = {}
    
    def add_result(self, request_hash: str, decision_type: str, primary_dest: str):
        """Record a result"""
        if request_hash not in self.request_cache:
            self.request_cache[request_hash] = []
        self.request_cache[request_hash].append({
            "decision_type": decision_type,
            "primary_dest": primary_dest
        })
    
    def detect_oscillations(self) -> dict:
        """Detect oscillations (same input, different outputs)"""
        oscillations = {}
        
        for request_hash, results in self.request_cache.items():
            if len(results) < 2:
                continue
            
            decisions = [r["decision_type"] for r in results]
            dests = [r["primary_dest"] for r in results]
            
            if len(set(decisions)) > 1 or len(set(dests)) > 1:
                oscillations[request_hash] = {
                    "decision_types": list(set(decisions)),
                    "primary_destinations": list(set(dests)),
                    "count": len(results)
                }
        
        return oscillations


# Export for use in test_validation.py
__all__ = [
    "SyntheticCaseGenerator",
    "ExpectationLibrary",
    "CaseExpectation",
    "CaseInput",
    "ValidationResult",
    "DecisionType",
    "Priority",
    "DistributionAnalyzer",
    "OscillationDetector",
]
