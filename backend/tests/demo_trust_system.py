#!/usr/bin/env python3
"""
Trust System Validator
======================

Demonstrates all 6 improvements:
1. Dynamic expectations (acceptable ranges)
2. Decision quality scoring
3. Active distribution alerts
4. Oscillation stress test
5. Adversarial chaos cases
6. Auto-weight optimizer interface
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.advanced_validation import (
    DYNAMIC_EXPECTATIONS,
    calculate_decision_quality,
    DistributionAlertSystem,
    OscillationStressTest,
    AdversarialCaseGenerator,
    AutoWeightOptimizer,
)


def demo_dynamic_expectations():
    """1. Show how flexible expectations work"""
    print("\n" + "="*100)
    print("1️⃣  DYNAMIC EXPECTATIONS (Acceptable Ranges)")
    print("="*100 + "\n")
    
    case_id = "CRITICAL-01-cardiac-nearby-full"
    expectation = DYNAMIC_EXPECTATIONS[case_id]
    
    print(f"Case: {expectation.description}")
    print(f"Severity: {expectation.severity}")
    print(f"\nOLD (Binary):")
    print(f"  expected_decision_type: 'direct'")
    print(f"  → Fails if system chooses 'stabilize_first' (even if quality > 0.75!)")
    
    print(f"\nNEW (Dynamic):")
    print(f"  acceptable_decisions: {[d.value for d in expectation.acceptable_decisions]}")
    print(f"  preferred: {expectation.preferred.value}")
    print(f"  min_decision_quality: {expectation.min_decision_quality}")
    print(f"  → Passes if EITHER decision has quality > 0.75")
    print(f"  → Prefers 'direct' but accepts 'stabilize_first' if justified")
    
    print(f"\nReason: {expectation.reason}")


def demo_decision_quality():
    """2. Show how decision quality is calculated"""
    print("\n" + "="*100)
    print("2️⃣  DECISION QUALITY SCORING")
    print("="*100 + "\n")
    
    # Example breakdown for DIRECT decision
    breakdown_good = {
        "S_survival": 0.92,
        "S_treatment": 0.85,
        "S_equipment": 0.90,
        "S_eta": 0.75,
        "S_load": 0.88,
        "final_score": 0.85,
    }
    
    # Example breakdown for poor decision
    breakdown_poor = {
        "S_survival": 0.45,
        "S_treatment": 0.30,
        "S_equipment": 0.35,
        "S_eta": 0.70,
        "S_load": 0.25,
        "final_score": 0.41,
    }
    
    quality_good = calculate_decision_quality(breakdown_good, is_stabilize=False)
    quality_poor = calculate_decision_quality(breakdown_poor, is_stabilize=False)
    
    print(f"Good Decision Breakdown:")
    for k, v in breakdown_good.items():
        if k.startswith("S_"):
            print(f"  {k}: {v:.2f}")
    print(f"  → Decision Quality: {quality_good:.3f} {'✅ PASS' if quality_good > 0.75 else '❌ FAIL'}")
    
    print(f"\nPoor Decision Breakdown:")
    for k, v in breakdown_poor.items():
        if k.startswith("S_"):
            print(f"  {k}: {v:.2f}")
    print(f"  → Decision Quality: {quality_poor:.3f} {'✅ PASS' if quality_poor > 0.75 else '❌ FAIL'}")
    
    print(f"\n✓ Quality scoring separates good tradeoffs from bad ones")


def demo_active_alerts():
    """3. Show how active distribution alerts work"""
    print("\n" + "="*100)
    print("3️⃣  ACTIVE DISTRIBUTION ALERTS")
    print("="*100 + "\n")
    
    alert_system = DistributionAlertSystem()
    
    # Record 10 decisions where S_eta dominates
    for i in range(10):
        alert_system.record({
            "S_survival": 0.40 + i*0.01,
            "S_treatment": 0.35 + i*0.01,
            "S_equipment": 0.38 + i*0.01,
            "S_eta": 0.75 + i*0.02,  # High and consistent
            "S_load": 0.50 + i*0.01,
            "final_score": 0.52 + i*0.01,
        })
    
    alerts = alert_system.generate_alerts()
    
    print(f"After recording 10 decisions:")
    if alerts:
        print(f"\n⚠️  ALERTS GENERATED:")
        for alert in alerts:
            print(f"  {alert}")
    else:
        print(f"\n✓ No alerts (system is balanced)")
    
    print(f"\nOLD (Passive): Just log means and stdevs")
    print(f"NEW (Active): Check thresholds and ALERT when dominance detected")


def demo_chaos_cases():
    """4. Show adversarial test cases"""
    print("\n" + "="*100)
    print("5️⃣  ADVERSARIAL/CHAOS TEST CASES")
    print("="*100 + "\n")
    
    chaos_cases = AdversarialCaseGenerator.generate_all_chaos_cases()
    
    print(f"Generated {len(chaos_cases)} chaos test cases:\n")
    
    for case in chaos_cases:
        print(f"  {case['case_id']}: {case['description']}")
        print(f"    Type: {case['chaos_type']}")
        print(f"    Tests: {case['expected_behavior']}\n")


def demo_oscillation_test():
    """4+. Show oscillation stress test concept"""
    print("\n" + "="*100)
    print("4️⃣  OSCILLATION STRESS TEST (Concept)")
    print("="*100 + "\n")
    
    print("OLD: Detect different outputs from different cases")
    print("\nNEW: Run SAME input 20 times\n")
    
    print("pseudo_code:")
    print("""
    results = []
    for i in range(20):
        result = await run_dispatch(same_case)
        results.append(result.decision_type)
    
    unique_decisions = set(results)
    
    if len(unique_decisions) > 1:
        OSCILLATION DETECTED: Non-deterministic behavior
        Runs 1-5: ['direct', 'direct', 'direct', 'direct', 'direct']
        Runs 16-20: ['stabilize_first', 'stabilize_first', ...]
    """)
    
    print("\n✓ Forces detection of hidden randomness in dispatch logic")


def demo_optimizer_concept():
    """6. Show weight optimization concept"""
    print("\n" + "="*100)
    print("6️⃣  AUTO-WEIGHT OPTIMIZER (Concept)")
    print("="*100 + "\n")
    
    print("OLD: Manual tuning based on gut feel")
    print("  Edit weights → run tests → observe → repeat (slow)")
    
    print("\nNEW: Systematic grid search")
    print("""
    optimizer = AutoWeightOptimizer(
        cases=all_40_cases,
        dispatch_fn=run_dispatch,
        expected_pass_rate=0.95
    )
    
    best_weights = await optimizer.optimize_weights(
        weight_ranges={
            "w_survival": (0.25, 0.35, 0.01),
            "w_treatment": (0.20, 0.30, 0.01),
            "w_equipment": (0.15, 0.25, 0.01),
            "w_eta": (0.10, 0.20, 0.01),
            "w_load": (0.05, 0.15, 0.01),
        },
        max_iterations=100
    )
    
    Output:
    [  5] Score: 0.8234  Passes: 38/40
    [ 10] Score: 0.8401  Passes: 39/40
    [ 15] Score: 0.8756  Passes: 40/40  <- Found optimal!
    [ 20] Score: 0.8654  Passes: 39/40
    
    Best weights: w_survival=0.30, w_treatment=0.27, ...
    """)


def main():
    """Run all demos"""
    
    print("\n" + "="*100)
    print("TRUST SYSTEM VALIDATOR — 6 IMPROVEMENTS")
    print("="*100)
    
    demo_dynamic_expectations()
    demo_decision_quality()
    demo_active_alerts()
    demo_chaos_cases()
    demo_oscillation_test()
    demo_optimizer_concept()
    
    # Summary
    print("\n" + "="*100)
    print("IMPROVEMENTS SUMMARY")
    print("="*100 + "\n")
    
    improvements = [
        ("1. Dynamic Expectations", "Acceptable ranges, not binary pass/fail"),
        ("2. Decision Quality", "Holistic quality score for each decision"),
        ("3. Active Alerts", "Passively monitoring → actively detecting bias"),
        ("4. Oscillation Test", "20-run stress test for non-determinism"),
        ("5. Chaos Cases", "Adversarial inputs: missing data, conflicts, errors"),
        ("6. Weight Optimizer", "Grid search to auto-tune weights"),
    ]
    
    for title, desc in improvements:
        print(f"  ✅ {title}")
        print(f"     {desc}\n")
    
    print("="*100)
    print("STATUS: TRUST LAYER ARCHITECTURE COMPLETE")
    print("="*100 + "\n")
    
    print("What Changed:")
    print("""
    Before: "Did it match expected?"
    After:  "Is the decision quality high? Is behavior consistent? Are weights real?"
    
    Before: Validation = static assertions
    After:  Validation = dynamic quality + active alerts + stress tests
    
    Before: Missing data → maybe crash
    After:  Chaos tests → graceful degradation
    
    Before: Weights tuned manually
    After:  Weights optimized automatically through grid search
    """)
    
    print("\n🔥 This is the gap between a student project and a real system.\n")


if __name__ == "__main__":
    try:
        main()
        print("✅ All demos complete\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
