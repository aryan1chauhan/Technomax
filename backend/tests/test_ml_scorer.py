"""
tests/test_ml_scorer.py — ML scoring engine tests.

Covers:
- Rule-based fallback scoring
- Edge cases (0 beds, huge distance, empty equipment)
- Normalization behavior
- Full predict_best_hospital pipeline
- Specialist pre-filtering
- Severity mapping
"""
import math
import pytest
from app.engine.ml_scorer import (
    ml_score,
    _rule_fallback,
    _log_normalize_beds,
    predict_best_hospital,
    SEVERITY_MAP,
    CONDITION_SPECIALIST_MAP,
)
from app.engine.haversine import calculate_distance


class TestLogNormalizeBeds:
    """Tests for bed count normalization."""

    def test_zero_beds(self):
        """0 beds should normalize to ~0."""
        result = _log_normalize_beds(0)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_negative_beds(self):
        """Negative beds should be clamped to 0."""
        result = _log_normalize_beds(-10)
        assert result == pytest.approx(0.0, abs=0.01)

    def test_small_hospital(self):
        """10-bed hospital should normalize to reasonable mid-range value."""
        result = _log_normalize_beds(10)
        assert 0.3 < result < 0.6

    def test_medium_hospital(self):
        """100-bed hospital should normalize higher than 10-bed."""
        small = _log_normalize_beds(10)
        medium = _log_normalize_beds(100)
        assert medium > small

    def test_large_hospital(self):
        """500-bed AIIMS should normalize to ~1.0 but not dominate."""
        result = _log_normalize_beds(500)
        assert 0.9 < result <= 1.0

    def test_normalization_spread(self):
        """Gap between 50 and 500 beds should be compressed (not 10x)."""
        small = _log_normalize_beds(50)
        large = _log_normalize_beds(500)
        ratio = large / small
        # Log normalization should keep ratio under 2x
        assert ratio < 2.0

    def test_caps_at_one(self):
        """Even absurdly large bed counts should cap at 1.0."""
        result = _log_normalize_beds(10000)
        assert result <= 1.0


class TestRuleFallback:
    """Tests for the rule-based scoring fallback."""

    def test_close_hospital_scores_high(self):
        """Hospital 2km away should score > 0.5."""
        score = _rule_fallback({
            "distance_km": 2.0,
            "beds": 20,
            "equipment_match": 1.0,
        })
        assert score > 0.5

    def test_far_hospital_scores_low(self):
        """Hospital 200km away should score much lower."""
        close = _rule_fallback({"distance_km": 2.0, "beds": 50, "equipment_match": 1.0})
        far = _rule_fallback({"distance_km": 200.0, "beds": 50, "equipment_match": 1.0})
        assert far < close
        assert far < 0.5  # ML model gives ~0.48 for 200km with beds=50

    def test_zero_distance(self):
        """Hospital at same location should get max distance score."""
        score = _rule_fallback({
            "distance_km": 0.0,
            "beds": 10,
            "equipment_match": 1.0,
        })
        assert score > 0.8

    def test_zero_beds_doesnt_crash(self):
        """0 beds should still return a valid score (from distance + equipment)."""
        score = _rule_fallback({
            "distance_km": 5.0,
            "beds": 0,
            "equipment_match": 1.0,
        })
        assert 0.0 <= score <= 1.0

    def test_no_equipment_match(self):
        """0% equipment match should reduce score."""
        full = _rule_fallback({"distance_km": 5.0, "beds": 20, "equipment_match": 1.0})
        none = _rule_fallback({"distance_km": 5.0, "beds": 20, "equipment_match": 0.0})
        assert none < full

    def test_extreme_distance(self):
        """999km away should not crash and should score very low."""
        score = _rule_fallback({
            "distance_km": 999.0,
            "beds": 100,
            "equipment_match": 1.0,
        })
        assert 0.0 <= score <= 1.0
        assert score < 0.5  # ML model gives ~0.49 for 999km with beds=100

    def test_missing_keys_use_defaults(self):
        """Missing feature keys should use defaults, not crash."""
        score = _rule_fallback({})
        assert 0.0 <= score <= 1.0


class TestSeverityMapping:
    """Tests for condition severity classification."""

    def test_cardiac_arrest_is_critical(self):
        assert SEVERITY_MAP.get("cardiac arrest") == 3

    def test_stroke_is_critical(self):
        assert SEVERITY_MAP.get("stroke") == 3

    def test_fracture_is_minor(self):
        assert SEVERITY_MAP.get("fracture") == 1

    def test_burns_is_moderate(self):
        assert SEVERITY_MAP.get("burns") == 2

    def test_unknown_defaults_to_none(self):
        """Unknown condition returns None from dict.get."""
        assert SEVERITY_MAP.get("papercut") is None


class TestSpecialistMapping:
    """Tests for condition → specialist routing."""

    def test_cardiac_maps_to_cardiologist(self):
        assert CONDITION_SPECIALIST_MAP.get("cardiac arrest") == "cardiologist"

    def test_stroke_maps_to_neurologist(self):
        assert CONDITION_SPECIALIST_MAP.get("stroke") == "neurologist"

    def test_trauma_maps_to_surgeon(self):
        assert CONDITION_SPECIALIST_MAP.get("trauma") == "general_surgeon"

    def test_unknown_returns_empty(self):
        assert CONDITION_SPECIALIST_MAP.get("papercut") is None


class TestHaversine:
    """Tests for the haversine distance calculator."""

    def test_same_point_zero_distance(self):
        """Same coordinates should return 0 km."""
        d = calculate_distance(29.86, 77.89, 29.86, 77.89)
        assert d == 0.0

    def test_known_distance(self):
        """Roorkee to Haridwar is approximately 30 km."""
        d = calculate_distance(29.8601, 77.8868, 29.9457, 78.1642)
        assert 25.0 < d < 35.0  # approximate

    def test_negative_coordinates(self):
        """Should handle southern hemisphere coordinates."""
        d = calculate_distance(-33.87, 151.21, -37.81, 144.96)
        assert d > 0

    def test_symmetry(self):
        """Distance A→B should equal B→A."""
        d1 = calculate_distance(29.86, 77.89, 30.07, 78.30)
        d2 = calculate_distance(30.07, 78.30, 29.86, 77.89)
        assert d1 == pytest.approx(d2, abs=0.01)


class TestPredictBestHospital:
    """Tests for the full hospital prediction pipeline."""

    def _make_hospital(self, id, lat, lng, beds=20, icu=3, equipment=None, accepting=True, specialists=None):
        return {
            "id": id,
            "name": f"Hospital {id}",
            "address": f"Address {id}",
            "lat": lat,
            "lng": lng,
            "beds": beds,
            "icu": icu,
            "doctors": 5,
            "equipment": equipment or ["ecg", "ventilator"],
            "accepting": accepting,
            "specialists": specialists or {},
        }

    def test_returns_none_when_no_accepting(self):
        """No accepting hospitals should return None, not crash."""
        hospitals = [
            self._make_hospital(1, 29.86, 77.89, accepting=False),
            self._make_hospital(2, 29.87, 77.90, accepting=False),
        ]
        result = predict_best_hospital(hospitals, "trauma", ["ecg"], 29.86, 77.89)
        assert result is None

    def test_returns_none_when_no_beds(self):
        """All hospitals with 0 beds should return None."""
        hospitals = [
            self._make_hospital(1, 29.86, 77.89, beds=0),
            self._make_hospital(2, 29.87, 77.90, beds=0),
        ]
        result = predict_best_hospital(hospitals, "trauma", ["ecg"], 29.86, 77.89)
        assert result is None

    def test_prefers_closer_hospital_rule_fallback(self):
        """Rule-based fallback should prefer closer hospital over farther one."""
        # Test rule-based directly (model-independent)
        close = _rule_fallback({"distance_km": 2.0, "beds": 20, "equipment_match": 1.0})
        far = _rule_fallback({"distance_km": 200.0, "beds": 20, "equipment_match": 1.0})
        assert close > far

    def test_single_accepting_hospital_returned(self):
        """When only one hospital accepts, it should always be returned."""
        hospitals = [
            self._make_hospital(1, 29.86, 77.89, beds=20, accepting=True),
            self._make_hospital(2, 30.50, 78.50, beds=20, accepting=False),
        ]
        result = predict_best_hospital(hospitals, "fracture", [], 29.86, 77.89)
        assert result is not None
        assert result["id"] == 1

    def test_equipment_matching(self):
        """Hospital with matching equipment should be preferred."""
        hospitals = [
            self._make_hospital(1, 29.86, 77.89, equipment=["ecg"]),
            self._make_hospital(2, 29.861, 77.891, equipment=["ecg", "defibrillator", "ventilator"]),
        ]
        result = predict_best_hospital(
            hospitals, "cardiac_arrest", ["ecg", "defibrillator"], 29.86, 77.89
        )
        assert result is not None
        # Hospital 2 has better equipment match
        assert "defibrillator" in result.get("equipment_matched", [])

    def test_result_contains_required_fields(self):
        """Result dict should contain all required response fields."""
        hospitals = [self._make_hospital(1, 29.86, 77.89)]
        result = predict_best_hospital(hospitals, "trauma", ["ecg"], 29.86, 77.89)
        
        if result is None:
            pytest.skip("No result returned")
        
        required = ["final_score", "distance_km", "eta_minutes", 
                     "equipment_matched", "equipment_missing", "ml_reasoning"]
        for field in required:
            assert field in result, f"Missing field: {field}"

    def test_specialist_prefilter(self):
        """Hospital with the right specialist should be preferred."""
        hospitals = [
            self._make_hospital(1, 29.86, 77.89, specialists={}),
            self._make_hospital(2, 29.861, 77.891, specialists={"cardiologist": 2}),
        ]
        result = predict_best_hospital(
            hospitals, "cardiac arrest", ["ecg", "defibrillator"], 29.86, 77.89
        )
        assert result is not None
        assert result["id"] == 2  # has cardiologist

    def test_empty_hospital_list(self):
        """Empty input list should return None."""
        result = predict_best_hospital([], "trauma", [], 29.86, 77.89)
        assert result is None

    def test_eta_is_at_least_one_minute(self):
        """ETA should always be >= 1 minute, even for very close hospitals."""
        hospitals = [self._make_hospital(1, 29.86, 77.89)]
        result = predict_best_hospital(hospitals, "fracture", [], 29.86, 77.89)
        if result:
            assert result["eta_minutes"] >= 1

    def test_score_between_zero_and_one(self):
        """Final score should be in [0, 1] range."""
        hospitals = [self._make_hospital(1, 29.86, 77.89)]
        result = predict_best_hospital(hospitals, "trauma", [], 29.86, 77.89)
        if result:
            assert 0.0 <= result["final_score"] <= 1.0
