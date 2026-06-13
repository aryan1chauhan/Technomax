"""Test ML calibration and scoring inside the container."""
import math
from app.engine.ml_scorer import score_hospital, _calibrate_ml_confidence

# Test calibration function directly
print("=== ML Confidence Calibration Table ===")
for raw in [0.05, 0.10, 0.125, 0.15, 0.19, 0.25, 0.30, 0.40, 0.50]:
    cal = _calibrate_ml_confidence(raw)
    print(f"  raw={raw:.3f} -> calibrated={cal:.3f} ({cal*100:.0f}%)")

print()

# Test a real scoring call
result = score_hospital(
    hospital_id=1,
    ambulance_lat=30.3165,
    ambulance_lon=78.0322,
    hospital_lat=30.3255,
    hospital_lon=78.0410,
    condition="allergic_reaction",
    available_beds=17,
    icu_beds=3,
    total_beds=30,
    hospital_equipment=["ventilator", "defibrillator", "ct_scan", "blood_bank"],
    required_equipment=["defibrillator"],
    specialist_count=2,
    hospital_load=0.3,
    historical_success_rate=0.85,
)

bd = result.get("score_breakdown", {})
print("=== Hospital Score Result ===")
print(f"  Overall score         : {result['score']:.2%}")
print(f"  ML used               : {result['ml_used']}")
print(f"  ML confidence (cal)   : {bd.get('ml_confidence', 'N/A')}")
print(f"  ML confidence (raw)   : {bd.get('ml_confidence_raw', 'N/A')}")
print(f"  Interpretable score   : {bd.get('interpretable_score', 'N/A')}")
print(f"  Distance score        : {bd.get('distance_score', 'N/A')}")
print(f"  Bed score (model)     : {bd.get('bed_score', 'N/A')}")
print(f"  Equipment match       : {bd.get('equipment_match', 'N/A')}")
print(f"  Specialist present    : {bd.get('specialist_present', 'N/A')}")
print(f"  Explanation           : {result.get('explanation', '')}")
print(f"  Pros                  : {result.get('pros', [])}")
print(f"  Cons                  : {result.get('cons', [])}")

# Test regional bed display normalization
avail = 17
beds_display = round(min(1.0, math.log1p(avail) / math.log1p(50)), 4)
beds_model = round(math.log1p(avail) / math.log1p(501), 4)
print()
print("=== Bed Score Comparison ===")
print(f"  Model normalization (502 scale) : {beds_model:.2%}")
print(f"  Display normalization (50 scale): {beds_display:.2%}")
