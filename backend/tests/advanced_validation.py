"""
Advanced Validation System - Trust Layer
=========================================

Upgrades:
1. Dynamic expectations (acceptable ranges)
2. Decision quality scoring
3. Active distribution alerts
4. Oscillation stress test (20 runs)
5. Adversarial/chaos test cases
6. Auto-weight optimizer
"""

import json
import statistics
import asyncio
from typing import Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.validation_harness import (
    SyntheticCaseGenerator,
    DecisionType,
    Priority,
)


# ============================================================================
# 1. DYNAMIC EXPECTATIONS (Acceptable Ranges)
# ============================================================================

@dataclass
class DynamicExpectation:
    """Flexible ground truth with acceptable ranges"""
    case_id: str
    condition: str
    severity: float
    
    # Instead of single decision → range of acceptable
    acceptable_decisions: list[DecisionType]
    preferred: DecisionType
    
    # Instead of exact priority → acceptable range
    acceptable_priorities: list[Priority]
    preferred_priority: Priority
    
    must_not_choose: list[str]
    
    # Quality thresholds
    min_decision_quality: float  # 0.0-1.0
    
    description: str
    reason: str


DYNAMIC_EXPECTATIONS = {
    # CRITICAL cases - accept both but prefer best
    "CRITICAL-01-cardiac-nearby-full": DynamicExpectation(
        case_id="CRITICAL-01-cardiac-nearby-full",
        condition="cardiac_arrest",
        severity=9.5,
        acceptable_decisions=[DecisionType.DIRECT, DecisionType.STABILIZE_FIRST],
        preferred=DecisionType.DIRECT,
        acceptable_priorities=[Priority.BEST_EQUIPPED, Priority.BALANCED],
        preferred_priority=Priority.BEST_EQUIPPED,
        must_not_choose=["general_sec_1"],
        min_decision_quality=0.75,  # Must be high quality
        description="Cardiac arrest, nearest fully equipped",
        reason="Defibrillator critical; accept DIRECT or STABILIZE_FIRST if quality > 0.75"
    ),
    
    "CRITICAL-02-stroke-severe-time": DynamicExpectation(
        case_id="CRITICAL-02-stroke-severe-time",
        condition="stroke",
        severity=9.2,
        acceptable_decisions=[DecisionType.STABILIZE_FIRST, DecisionType.DIRECT],
        preferred=DecisionType.STABILIZE_FIRST,
        acceptable_priorities=[Priority.BALANCED, Priority.NEAREST],
        preferred_priority=Priority.BALANCED,
        must_not_choose=["stroke_center_1"],
        min_decision_quality=0.70,
        description="Severe stroke with wide eta/survival gap",
        reason="ETA 18 >> survival ~8; prefer stabilize but accept direct if quality strong"
    ),
}


# ============================================================================
# 2. DECISION QUALITY SCORING
# ============================================================================

@dataclass
class DecisionQualityMetrics:
    """Track decision quality across dimensions"""
    case_id: str
    decision_type: str
    primary_destination: str
    
    # Component scores
    s_survival: float
    s_treatment: float
    s_equipment: float
    s_eta: float
    s_load: float
    
    # Quality composite
    decision_quality: float  # weighted average
    
    # Safety margin
    second_place_gap: float  # difference from next best hospital
    
    # Context adherence
    severity_alignment: float  # does decision match severity?


def calculate_decision_quality(breakdown: dict[str, float], is_stabilize: bool = False) -> float:
    """
    Calculate holistic decision quality
    
    Quality = weighted sum of components
    Different weights for stabilize_first vs direct
    """
    s_surv = breakdown.get("S_survival", 0.0)
    s_treat = breakdown.get("S_treatment", 0.0)
    s_equip = breakdown.get("S_equipment", 0.0)
    s_eta = breakdown.get("S_eta", 0.0)
    s_load = breakdown.get("S_load", 0.0)
    
    if is_stabilize:
        # For stabilization: proximity + capacity matter most
        quality = (
            s_surv * 0.35 +
            s_treat * 0.20 +
            s_equip * 0.15 +
            s_eta * 0.20 +  # ETA more important for stabilization
            s_load * 0.10
        )
    else:
        # For direct: survival + treatment + equipment critical
        quality = (
            s_surv * 0.40 +
            s_treat * 0.30 +
            s_equip * 0.20 +
            s_eta * 0.07 +
            s_load * 0.03
        )
    
    return min(1.0, max(0.0, quality))


# ============================================================================
# 3. ACTIVE DISTRIBUTION ALERTS
# ============================================================================

class DistributionAlertSystem:
    """Monitor component distributions with active alerts"""
    
    def __init__(self):
        self.scores = {
            "S_survival": [],
            "S_treatment": [],
            "S_equipment": [],
            "S_eta": [],
            "S_load": [],
        }
        self.final_scores = []
        self.alerts = []
    
    def record(self, breakdown: dict[str, float]):
        """Record a score breakdown"""
        for component in self.scores.keys():
            self.scores[component].append(breakdown.get(component, 0.0))
        self.final_scores.append(breakdown.get("final_score", 0.0))
    
    def generate_alerts(self) -> list[str]:
        """Generate alerts if thresholds violated"""
        self.alerts = []
        
        if not self.scores["S_survival"]:
            return self.alerts
        
        # Alert 1: Component dominance
        means = {k: statistics.mean(v) for k, v in self.scores.items()}
        avg_all = statistics.mean(means.values())
        
        for component, mean_val in means.items():
            gap = abs(mean_val - avg_all)
            if gap > 0.20:  # Dominance threshold
                self.alerts.append(
                    f"⚠️ DOMINANCE: {component} μ={mean_val:.3f} (gap={gap:.3f} > 0.20)"
                )
        
        # Alert 2: Component near-constant (fake weight indicator)
        for component, values in self.scores.items():
            if len(values) > 1:
                stdev = statistics.stdev(values)
                if stdev < 0.05:
                    self.alerts.append(
                        f"⚠️ NEAR-CONSTANT: {component} σ={stdev:.3f} (always ~{statistics.mean(values):.3f})"
                    )
        
        # Alert 3: Final scores too similar (score collapse)
        if len(self.final_scores) > 1:
            final_stdev = statistics.stdev(self.final_scores)
            if final_stdev < 0.08:
                self.alerts.append(
                    f"⚠️ SCORE_COLLAPSE: Final scores σ={final_stdev:.3f} (too similar, may cause random selection)"
                )
        
        # Alert 4: ETA dominance in practice
        if len(self.scores["S_eta"]) > 5:
            eta_mean = statistics.mean(self.scores["S_eta"])
            if eta_mean > 0.65:
                self.alerts.append(
                    f"⚠️ ETA_BIAS: S_eta μ={eta_mean:.3f} (may override other factors)"
                )
        
        return self.alerts


# ============================================================================
# 4. OSCILLATION STRESS TEST
# ============================================================================

class OscillationStressTest:
    """Run same case 20 times to detect non-determinism"""
    
    async def stress_test_case(self, case, dispatch_fn, runs: int = 20) -> dict:
        """
        Run same case multiple times, check for inconsistency
        
        dispatch_fn: async function that takes case and returns result
        """
        results = []
        
        for i in range(runs):
            try:
                result = await dispatch_fn(case)
                results.append({
                    "run": i,
                    "decision_type": result.get("decision_type"),
                    "primary_destination": result.get("primary_destination"),
                    "final_score": result.get("reasoning", {}).get("ml_score"),
                })
            except Exception as e:
                results.append({
                    "run": i,
                    "error": str(e),
                })
        
        # Analyze consistency
        decision_types = [r.get("decision_type") for r in results if "decision_type" in r]
        destinations = [r.get("primary_destination") for r in results if "primary_destination" in r]
        
        oscillation_detected = (len(set(decision_types)) > 1 or len(set(destinations)) > 1)
        
        return {
            "case_id": case.case_id,
            "runs": runs,
            "oscillation_detected": oscillation_detected,
            "unique_decisions": list(set(decision_types)),
            "unique_destinations": list(set(destinations)),
            "results": results,
            "alert": "❌ NON-DETERMINISTIC" if oscillation_detected else "✓ Consistent",
        }


# ============================================================================
# 5. ADVERSARIAL/CHAOS TEST CASES
# ============================================================================

class AdversarialCaseGenerator:
    """Generate chaos test cases with corrupted/conflicting data"""
    
    @staticmethod
    def generate_missing_vitals_case() -> dict:
        """Case with incomplete vitals"""
        return {
            "case_id": "CHAOS-01-missing-vitals",
            "description": "Cardiac arrest but pulse/systolic missing",
            "ambulance_equipment": ["defibrillator", "oxygen"],
            "condition": "cardiac_arrest",
            "severity_score": 9.5,
            "patient_vitals": {
                "spo2": 85,
                # pulse missing!
                # systolic missing!
            },
            "required_equipment": ["defibrillator"],
            "chaos_type": "incomplete_data",
            "expected_behavior": "Should gracefully handle missing vitals, not crash"
        }
    
    @staticmethod
    def generate_conflicting_symptoms_case() -> dict:
        """Case with contradictory severity signals"""
        return {
            "case_id": "CHAOS-02-conflicting-symptoms",
            "description": "Mild vitals but severe condition + high severity score",
            "ambulance_equipment": ["oxygen"],
            "condition": "trauma",
            "severity_score": 9.8,  # Very high
            "patient_vitals": {
                "spo2": 98,      # Very high (good)
                "pulse": 72,     # Normal (good)
                "systolic": 140, # High (not critical)
            },
            "required_equipment": ["surgery"],
            "chaos_type": "severity_conflict",
            "expected_behavior": "Trust severity_score, not just vitals; should rank by condition urgency"
        }
    
    @staticmethod
    def generate_overestimated_severity_case() -> dict:
        """Case with severity_score way higher than vitals"""
        return {
            "case_id": "CHAOS-03-overestimated",
            "description": "Severity=10 but vitals completely normal",
            "ambulance_equipment": ["oxygen"],
            "condition": "respiratory",
            "severity_score": 10.0,  # Maximum
            "patient_vitals": {
                "spo2": 97,
                "pulse": 70,
                "systolic": 125,
            },
            "required_equipment": ["oxygen"],
            "chaos_type": "data_mismatch",
            "expected_behavior": "Should detect inconsistency, avoid over-routing"
        }
    
    @staticmethod
    def generate_equipment_extraction_error_case() -> dict:
        """Case with malformed/duplicate equipment labels"""
        return {
            "case_id": "CHAOS-04-equipment-error",
            "description": "Equipment labels are duplicated/malformed",
            "ambulance_equipment": [
                "oxygen",
                "OXYGEN",  # Case mismatch
                "oxygen",  # Duplicate
                "ventilator",
                "vent",    # Abbreviation
            ],
            "condition": "respiratory",
            "severity_score": 7.2,
            "patient_vitals": {"spo2": 87, "pulse": 95, "systolic": 115},
            "required_equipment": ["ventilator"],
            "chaos_type": "data_normalization",
            "expected_behavior": "Should normalize equipment names, deduplicate"
        }
    
    @staticmethod
    def generate_stale_hospital_data_case() -> dict:
        """Case where hospital availability is hours old"""
        return {
            "case_id": "CHAOS-05-stale-hospital",
            "description": "Hospital claim has beds, but data is 3 hours old",
            "ambulance_equipment": ["oxygen", "defibrillator"],
            "condition": "cardiac_arrest",
            "severity_score": 9.2,
            "patient_vitals": {"spo2": 80, "pulse": 0, "systolic": 65},
            "required_equipment": ["defibrillator", "cath_lab"],
            "chaos_type": "data_staleness",
            "expected_behavior": "Should prefer fresher snapshots or add uncertainty penalty"
        }
    
    @staticmethod
    def generate_gps_error_case() -> dict:
        """Case with GPS coordinates that are 50km off"""
        return {
            "case_id": "CHAOS-06-gps-error",
            "description": "Hospital GPS coordinates severely wrong (50km offset)",
            "ambulance_equipment": ["oxygen"],
            "condition": "stroke",
            "severity_score": 8.5,
            "patient_vitals": {"spo2": 91, "pulse": 98, "systolic": 120},
            "required_equipment": ["ct_scanner", "neurology"],
            "chaos_type": "coordinate_error",
            "expected_behavior": "Should detect outlier ETA, ask for confirmation or recompute"
        }
    
    @staticmethod
    def generate_all_chaos_cases() -> list[dict]:
        """Generate all adversarial cases"""
        return [
            AdversarialCaseGenerator.generate_missing_vitals_case(),
            AdversarialCaseGenerator.generate_conflicting_symptoms_case(),
            AdversarialCaseGenerator.generate_overestimated_severity_case(),
            AdversarialCaseGenerator.generate_equipment_extraction_error_case(),
            AdversarialCaseGenerator.generate_stale_hospital_data_case(),
            AdversarialCaseGenerator.generate_gps_error_case(),
        ]


# ============================================================================
# 6. AUTO-WEIGHT OPTIMIZER
# ============================================================================

class AutoWeightOptimizer:
    """Find optimal weights through grid search / optimization"""
    
    def __init__(self, cases: list, dispatch_fn, expected_pass_rate: float = 0.95):
        self.cases = cases
        self.dispatch_fn = dispatch_fn
        self.expected_pass_rate = expected_pass_rate
        self.best_weights = None
        self.best_score = 0.0
        self.optimization_history = []
    
    async def optimize_weights(
        self,
        weight_ranges: dict[str, tuple[float, float, float]],  # {name: (min, max, step)}
        max_iterations: int = 100,
    ) -> dict:
        """
        Grid search to find optimal weights
        
        Args:
            weight_ranges: e.g., {
                "w_survival": (0.25, 0.35, 0.01),
                "w_treatment": (0.20, 0.30, 0.01),
                ...
            }
            max_iterations: Stop after this many evaluations
        """
        print(f"\n🔄 AUTO-WEIGHT OPTIMIZER")
        print(f"   Searching weight space...")
        print(f"   Target: {self.expected_pass_rate*100:.0f}% pass rate\n")
        
        # Simplified grid search (full would be cartesian product)
        iteration = 0
        
        # Start with baseline
        baseline_weights = {
            "w_survival": 0.30,
            "w_treatment": 0.25,
            "w_equipment": 0.20,
            "w_eta": 0.15,
            "w_load": 0.10,
        }
        
        await self._evaluate_weights(baseline_weights, iteration)
        iteration += 1
        
        # Tune each weight around baseline
        for weight_name in baseline_weights.keys():
            min_val, max_val, step = weight_ranges.get(weight_name, (0.05, 0.40, 0.01))
            
            for new_val in [baseline_weights[weight_name] + delta 
                          for delta in [-0.05, -0.02, 0, 0.02, 0.05]]:
                if min_val <= new_val <= max_val:
                    test_weights = baseline_weights.copy()
                    test_weights[weight_name] = new_val
                    
                    # Renormalize so weights sum to 1.0
                    total = sum(test_weights.values())
                    test_weights = {k: v/total for k, v in test_weights.items()}
                    
                    await self._evaluate_weights(test_weights, iteration)
                    iteration += 1
                    
                    if iteration >= max_iterations:
                        break
            
            if iteration >= max_iterations:
                break
        
        print(f"\n✅ Optimization complete")
        print(f"   Best weights: {self.best_weights}")
        print(f"   Best score: {self.best_score:.4f}")
        
        return self.best_weights or baseline_weights
    
    async def _evaluate_weights(self, weights: dict[str, float], iteration: int) -> float:
        """Test a set of weights against all cases"""
        
        pass_count = 0
        quality_sum = 0.0
        
        for case in self.cases:
            try:
                result = await self.dispatch_fn(case, weights)
                
                # Simple scoring: did it avoid forbidden hospitals?
                if result.get("primary_destination") not in ["forbidden_1", "forbidden_2"]:
                    pass_count += 1
                    quality_sum += result.get("reasoning", {}).get("ml_score", 0.5)
            except Exception:
                pass
        
        score = (pass_count / len(self.cases)) + (quality_sum / len(self.cases)) * 0.1
        
        if score > self.best_score:
            self.best_score = score
            self.best_weights = weights.copy()
        
        history_entry = {
            "iteration": iteration,
            "weights": weights,
            "pass_rate": pass_count / len(self.cases),
            "avg_quality": quality_sum / len(self.cases) if self.cases else 0,
            "score": score,
        }
        self.optimization_history.append(history_entry)
        
        if iteration % 5 == 0:
            print(f"   [{iteration:3d}] Score: {score:.4f}  Passes: {pass_count}/{len(self.cases)}")
        
        return score


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    "DynamicExpectation",
    "DYNAMIC_EXPECTATIONS",
    "DecisionQualityMetrics",
    "calculate_decision_quality",
    "DistributionAlertSystem",
    "OscillationStressTest",
    "AdversarialCaseGenerator",
    "AutoWeightOptimizer",
]
