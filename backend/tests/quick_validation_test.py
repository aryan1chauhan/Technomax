#!/usr/bin/env python3
"""
Quick validation runner - Synchronous test executor
Directly instantiates cases and logs expected vs actual behavior
"""

import json
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.validation_harness import (
    SyntheticCaseGenerator,
    ExpectationLibrary,
    DistributionAnalyzer,
    OscillationDetector,
    DecisionType,
)


def run_quick_validation():
    """Quick validation without async dispatch calls"""
    
    print("\n" + "="*100)
    print("DECISION VALIDATION HARNESS — QUICK TEST")
    print("="*100 + "\n")
    
    # Generate all 40 test cases
    all_cases = SyntheticCaseGenerator.generate_all_cases()
    print(f"✓ Generated {len(all_cases)} test cases\n")
    
    # Show category breakdown
    categories = {
        "CRITICAL": [c for c in all_cases if c.case_id.startswith("CRITICAL")],
        "BORDERLINE": [c for c in all_cases if c.case_id.startswith("BORDERLINE")],
        "STABLE": [c for c in all_cases if c.case_id.startswith("STABLE")],
        "NO_MATCH": [c for c in all_cases if c.case_id.startswith("NO_MATCH")],
    }
    
    print("📊 TEST CASE DISTRIBUTION:")
    for cat_name, cat_cases in categories.items():
        print(f"  {cat_name:15s}  {len(cat_cases):2d} cases")
    print()
    
    # Show expectation definitions
    print("🎯 DEFINED EXPECTATIONS:")
    expectations = ExpectationLibrary.EXPECTATIONS
    print(f"  Total:         {len(expectations)}/{len(all_cases)} cases have ground truth")
    
    # Verify expectations cover critical cases
    critical_with_expected = sum(1 for c in categories["CRITICAL"] 
                                if c.case_id in expectations)
    print(f"  Critical:      {critical_with_expected}/10 cases have ground truth")
    print()
    
    # Show case details
    print("📋 SAMPLE CASES:")
    for i, case in enumerate(all_cases[:3], 1):
        expectation = expectations.get(case.case_id)
        print(f"\n  Case {i}: {case.case_id}")
        print(f"    Condition:   {case.condition} (severity={case.severity_score})")
        print(f"    Hospitals:   {len(case.hospitals)} options")
        if expectation:
            print(f"    Expected:    {expectation.expected_decision_type.value} ({expectation.expected_priority.value})")
            print(f"    Reason:      {expectation.reason}")
        else:
            print(f"    Expected:    [NOT DEFINED]")
    print()
    
    # Show analyzer capability
    analyzer = DistributionAnalyzer()
    print("📈 DISTRIBUTION ANALYZER (example recording):")
    analyzer.record({
        "S_survival": 0.95,
        "S_treatment": 0.80,
        "S_equipment": 0.75,
        "S_eta": 0.68,
        "S_load": 0.92,
        "final_score": 0.805,
    })
    analyzer.record({
        "S_survival": 0.72,
        "S_treatment": 0.85,
        "S_equipment": 0.68,
        "S_eta": 0.55,
        "S_load": 0.88,
        "final_score": 0.718,
    })
    
    report = analyzer.report()
    print(f"  Recorded 2 score breakdowns")
    print(f"  S_survival:  μ={report['S_survival']['mean']:.3f}  σ={report['S_survival']['stdev']:.3f}")
    print(f"  S_treatment: μ={report['S_treatment']['mean']:.3f}  σ={report['S_treatment']['stdev']:.3f}")
    print(f"  S_equipment: μ={report['S_equipment']['mean']:.3f}  σ={report['S_equipment']['stdev']:.3f}")
    print(f"  S_eta:       μ={report['S_eta']['mean']:.3f}  σ={report['S_eta']['stdev']:.3f}")
    print(f"  S_load:      μ={report['S_load']['mean']:.3f}  σ={report['S_load']['stdev']:.3f}")
    
    dominance = analyzer.detect_dominance()
    print(f"\n  Weight Dominance Check:")
    for component, analysis in dominance.items():
        status = "⚠️  HIGH GAP" if analysis["dominates"] else "✓ balanced"
        print(f"    {component:15s}  gap={analysis['gap']:.3f}  {status}")
    print()
    
    # Show oscillation detector
    oscillator = OscillationDetector()
    print("🔄 OSCILLATION DETECTOR (example scenarios):")
    
    req_hash = "abc123def456"
    oscillator.add_result(req_hash, "direct", "hospital_1")
    oscillator.add_result(req_hash, "direct", "hospital_1")  # Same
    
    req_hash2 = "xyz789uvw321" 
    oscillator.add_result(req_hash2, "direct", "hospital_2")
    oscillator.add_result(req_hash2, "stabilize_first", "hospital_3")  # Different!
    
    oscillations = oscillator.detect_oscillations()
    print(f"  Recorded 4 results across 2 request patterns")
    print(f"  Oscillations found: {len(oscillations)}")
    if oscillations:
        for req_hash, osc in oscillations.items():
            print(f"    {req_hash[:8]}... → decisions={osc['decision_types']}, "
                  f"dests={osc['primary_destinations']}")
    print()
    
    # Test expectations
    print("🔍 EXPECTATION LIBRARY TEST:")
    test_case_id = "CRITICAL-01-cardiac-nearby-full"
    expectation = ExpectationLibrary.get_expectation(test_case_id)
    if expectation:
        print(f"  ✓ Found expectation for {test_case_id}")
        print(f"    Decision:    {expectation.expected_decision_type.value}")
        print(f"    Priority:    {expectation.expected_priority.value}")
        print(f"    Forbidden:   {expectation.must_not_choose}")
    else:
        print(f"  ✗ No expectation found for {test_case_id}")
    print()
    
    # Summary
    print("="*100)
    print("✓ VALIDATION FRAMEWORK READY")
    print("="*100)
    print("""
Key Components:
  1️⃣  SyntheticCaseGenerator    → 40 diverse test cases
  2️⃣  ExpectationLibrary        → Ground truth definitions  
  3️⃣  DistributionAnalyzer      → Weight & component tracking
  4️⃣  OscillationDetector       → Consistency validation
  5️⃣  ValidationRunner          → Full harness executor

Ready to run against dispatch engine with:
  - Decision type assertions
  - Forbidden hospital checks
  - Score component distribution analysis
  - Oscillation detection (same input → different outputs)
  - Weight dominance detection
  
Next: Run actual dispatch requests through this harness →
     python -m pytest tests/test_validation.py
""")
    
    return True


if __name__ == "__main__":
    try:
        success = run_quick_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
