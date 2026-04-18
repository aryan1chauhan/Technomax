"""
Test Validation Runner
=====================

Execute all 40 cases, assert expectations, detect pathological behavior
"""

import sys
import json
import hashlib
from typing import Optional
from pathlib import Path
from dataclasses import asdict

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# from app.main import app  # Removed to prevent DB connection during pure engine tests

from app.engine.dispatch_engine import run_dispatch
from tests.validation_harness import (
    SyntheticCaseGenerator,
    ExpectationLibrary,
    ValidationResult,
    DistributionAnalyzer,
    OscillationDetector,
)


class ValidationRunner:
    """Execute validation harness against dispatch engine"""
    
    def __init__(self):
        self.results = []
        self.analyzer = DistributionAnalyzer()
        self.oscillator = OscillationDetector()
        self.case_count = 0
        self.passed_count = 0
        self.failed_count = 0
    
    async def run_case(self, case_input) -> ValidationResult:
        """Execute one case through dispatch engine"""
        
        # Mock dispatch call (in real deployment, this would be async to actual API)
        # For now, we'll call the dispatch_engine directly
        
        try:
            result = await run_dispatch(
                hospitals=case_input.hospitals,
                ambulance_equipment=case_input.ambulance_equipment,
                condition_type=case_input.condition,
                severity_score=case_input.severity_score,
                vitals=case_input.patient_vitals,
                required_equipment=case_input.required_equipment,
                ambulance_lat=case_input.ambulance_lat,
                ambulance_lng=case_input.ambulance_lng,
            )
            
            # Get expectation
            expectation = ExpectationLibrary.get_expectation(case_input.case_id)
            
            primary_dest = result.get("primary_destination", "unknown")
            primary_dest_id = primary_dest.get("hospital_id", "unknown") if isinstance(primary_dest, dict) else primary_dest
            
            # Build validation result
            validation_result = ValidationResult(
                case_id=case_input.case_id,
                passed=True,
                decision_type_match=False,
                priority_match=False,
                forbidden_hospital_avoided=True,
                decision_type_actual=result.get("decision_type", "unknown"),
                primary_destination=primary_dest_id,
                score_breakdown={},
                issues=[]
            )
            
            # Check decision type
            if expectation:
                if result.get("decision_type") != expectation.expected_decision_type.value:
                    validation_result.issues.append(
                        f"Decision type mismatch: expected {expectation.expected_decision_type.value}, "
                        f"got {result.get('decision_type')}"
                    )
                else:
                    validation_result.decision_type_match = True
                
                # Check forbidden hospitals
                if primary_dest_id in expectation.must_not_choose:
                    validation_result.forbidden_hospital_avoided = False
                    validation_result.issues.append(
                        f"Chose forbidden hospital: {primary_dest_id}"
                    )
            else:
                validation_result.issues.append("No expectation defined for this case")
            
            # Extract score breakdown from reasoning if present
            if "reasoning" in result:
                reasoning = result["reasoning"]
                validation_result.score_breakdown = {
                    k: v for k, v in reasoning.items()
                    if k.startswith("S_") or k == "final_score"
                }
                # Also pull from nested breakdown if engine provided it
                if "score_breakdown" in reasoning and isinstance(reasoning["score_breakdown"], dict):
                    validation_result.score_breakdown.update({
                        k: v for k, v in reasoning["score_breakdown"].items()
                        if k.startswith("S_") or k == "final_score"
                    })
                
                self.analyzer.record(validation_result.score_breakdown)
            
            # Record for oscillation detection
            request_hash = hashlib.md5(
                json.dumps({
                    "condition": case_input.condition,
                    "severity": case_input.severity_score,
                    "hospitals_count": len(case_input.hospitals),
                }, sort_keys=True).encode()
            ).hexdigest()
            self.oscillator.add_result(
                request_hash,
                result.get("decision_type", "unknown"),
                primary_dest_id
            )
            
            # Final pass/fail
            if validation_result.issues:
                validation_result.passed = False
                self.failed_count += 1
            else:
                self.passed_count += 1
            
            self.case_count += 1
            return validation_result
            
        except Exception as e:
            self.case_count += 1
            self.failed_count += 1
            return ValidationResult(
                case_id=case_input.case_id,
                passed=False,
                decision_type_match=False,
                priority_match=False,
                forbidden_hospital_avoided=False,
                decision_type_actual="error",
                primary_destination="error",
                score_breakdown={},
                issues=[f"Exception: {str(e)}"]
            )
    
    async def run_all_cases(self) -> dict:
        """Execute all 40 test cases"""
        
        print("\n" + "="*80)
        print("VALIDATION HARNESS — COMPREHENSIVE DISPATCH AUDIT")
        print("="*80 + "\n")
        
        all_cases = SyntheticCaseGenerator.generate_all_cases()
        
        print(f"📊 Executing {len(all_cases)} test cases...")
        print(f"  - 10 Critical (unstable)")
        print(f"  - 10 Borderline (tight decisions)")
        print(f"  - 10 Stable (clear choices)")
        print(f"  - 10 No Perfect Match (forced decisions)")
        print("\n")
        
        for i, case in enumerate(all_cases, 1):
            result = await self.run_case(case)
            self.results.append(result)
            
            status = "✓ PASS" if result.passed else "✗ FAIL"
            print(f"[{i:2d}/40] {case.case_id:40s} {status}")
            
            if result.issues:
                for issue in result.issues:
                    print(f"         → {issue}")
        
        return self.generate_report()
    
    def generate_report(self) -> dict:
        """Generate comprehensive validation report"""
        
        print("\n" + "="*80)
        print("VALIDATION REPORT")
        print("="*80 + "\n")
        
        # Summary statistics
        print(f"📊 RESULTS SUMMARY")
        print(f"  Total cases:     {self.case_count}")
        if self.case_count > 0:
            print(f"  Passed:          {self.passed_count} ({100*self.passed_count/self.case_count:.1f}%)")
            print(f"  Failed:          {self.failed_count} ({100*self.failed_count/self.case_count:.1f}%)")
        else:
            print("  No cases executed")
        print()
        
        # Distribution analysis
        print(f"📈 SCORE COMPONENT DISTRIBUTION")
        dist_report = self.analyzer.report()
        for component, stats in dist_report.items():
            print(f"  {component:15s}  μ={stats['mean']:.3f}  σ={stats['stdev']:.3f}  "
                  f"[{stats['min']:.3f}, {stats['max']:.3f}]")
        print()
        
        # Dominance analysis
        print(f"⚠️  WEIGHT DOMINANCE CHECK")
        dominance = self.analyzer.detect_dominance()
        for component, analysis in dominance.items():
            status = "⚠️  DOMINATES" if analysis["dominates"] else "  ✓ balanced"
            print(f"  {component:15s}  gap={analysis['gap']:.3f}  {status}")
        print()
        
        # Oscillation analysis
        print(f"🔄 OSCILLATION DETECTION")
        oscillations = self.oscillator.detect_oscillations()
        if oscillations:
            print(f"  ⚠️  Found {len(oscillations)} oscillating request patterns:")
            for hash_val, osc_data in list(oscillations.items())[:5]:
                print(f"     {hash_val[:8]}...  decisions={osc_data['decision_types']}  "
                      f"dests={osc_data['primary_destinations']}")
                if len(oscillations) > 5:
                    print(f"     ... and {len(oscillations) - 5} more")
                    break
        else:
            print(f"  ✓ No oscillations detected")
        print()
        
        # Failure analysis
        print(f"❌ FAILURE ANALYSIS")
        if self.failed_count > 0:
            failure_types = {}
            for result in self.results:
                if not result.passed:
                    for issue in result.issues:
                        issue_type = issue.split(":")[0]
                        failure_types[issue_type] = failure_types.get(issue_type, 0) + 1
            
            for issue_type, count in sorted(failure_types.items(), key=lambda x: -x[1]):
                print(f"  {issue_type:40s}  {count:3d} cases")
        else:
            print(f"  ✓ All cases passed!")
        print()
        
        # Tie-breaker effectiveness
        print(f"🔗 TIE-BREAKER ANALYSIS")
        score_diffs = []
        for result in self.results:
            if "final_score" in result.score_breakdown:
                score_diffs.append(abs(result.score_breakdown["final_score"]))
        
        if score_diffs:
            tie_count = sum(1 for diff in score_diffs if diff < 0.05)
            print(f"  Cases with score diff < 0.05:  {tie_count} ({100*tie_count/len(score_diffs):.1f}%)")
            print(f"  Avg final score:               {sum(score_diffs)/len(score_diffs):.3f}")
            print(f"  Min/Max final score:           {min(score_diffs):.3f} / {max(score_diffs):.3f}")
        print()
        
        # Category breakdown
        print(f"📋 CATEGORY BREAKDOWN")
        categories = {
            "CRITICAL": [r for r in self.results if r.case_id.startswith("CRITICAL")],
            "BORDERLINE": [r for r in self.results if r.case_id.startswith("BORDERLINE")],
            "STABLE": [r for r in self.results if r.case_id.startswith("STABLE")],
            "NO_MATCH": [r for r in self.results if r.case_id.startswith("NO_MATCH")],
        }
        
        for cat_name, cat_results in categories.items():
            if cat_results:
                passed = sum(1 for r in cat_results if r.passed)
                pct = 100 * passed / len(cat_results)
                print(f"  {cat_name:15s}  {passed:2d}/{len(cat_results):2d} passed  ({pct:5.1f}%)")
        print()
        
        # Critical recommendations
        print(f"🎯 CRITICAL FINDINGS")
        if self.failed_count > 5:
            print(f"  ⚠️  {self.failed_count} failed cases — review weight tuning")
        if dominance.get("S_eta", {}).get("dominates"):
            print(f"  ⚠️  S_eta dominates — ETA weight may be too high")
        if oscillations:
            print(f"  ⚠️  Oscillations detected — non-deterministic behavior found")
        if not oscillations and self.failed_count <= 5:
            print(f"  ✓ System shows consistent, defensible decision-making")
        print()
        
        return {
            "summary": {
                "total": self.case_count,
                "passed": self.passed_count,
                "failed": self.failed_count,
                "pass_rate": self.passed_count / self.case_count if self.case_count > 0 else 0,
            },
            "distribution": dist_report,
            "dominance": dominance,
            "oscillations": oscillations,
            "results": [asdict(r) for r in self.results],
        }


async def main():
    """Main entry point"""
    runner = ValidationRunner()
    report = await runner.run_all_cases()
    
    # Save report
    report_path = Path(__file__).parent / "validation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"📁 Report saved to: {report_path}")
    
    return report


if __name__ == "__main__":
    import asyncio
    result = asyncio.run(main())
    sys.exit(0 if result["summary"]["pass_rate"] >= 0.9 else 1)
