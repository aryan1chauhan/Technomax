"""
tests/test_ml_scorer.py
-----------------------
Pytest suite for the hybrid hospital matchmaking engine.

Covers:
  - Normalisation helpers (boundaries + mid-range)
  - Haversine distance against known coordinates
  - Feature vector shape and value correctness
  - score_hospital: output contract, ML-off path, zero-capacity edge
  - rank_hospitals: ordering, enrichment, ties, empty input
  - Fallback: weighted formula produces a valid score without the pickle
"""

import math
import sys
import types
import pytest
from pathlib import Path

import joblib

# ---------------------------------------------------------------------------
# Inline the module under test so the suite runs without a full FastAPI stack.
# We patch the pickle load to simulate "model not found" (the normal CI path).
# ---------------------------------------------------------------------------

import importlib, unittest.mock

# Stub out the pickle load so the module imports cleanly with _ML_AVAILABLE=False
with unittest.mock.patch("builtins.open", side_effect=FileNotFoundError):
    with unittest.mock.patch("pathlib.Path.open", side_effect=FileNotFoundError):
        if "app.engine.ml_scorer" in sys.modules:
            del sys.modules["app.engine.ml_scorer"]
        if "ml_scorer" in sys.modules:
            del sys.modules["ml_scorer"]
        sys.path.insert(0, ".")
        try:
            from app.engine.ml_scorer import (
                normalize_distance, log_normalize_beds, normalize_icu,
                haversine_km, _build_feature_vector, _weighted_score,
                score_hospital, rank_hospitals,
                CONDITION_SEVERITY_MAP, _FEATURE_COLUMNS, _ML_AVAILABLE,
            )
            import app.engine.ml_scorer as scorer
        except ModuleNotFoundError:
            sys.path.insert(0, "..")
            from app.engine.ml_scorer import (
                normalize_distance, log_normalize_beds, normalize_icu,
                haversine_km, _build_feature_vector, _weighted_score,
                score_hospital, rank_hospitals,
                CONDITION_SEVERITY_MAP, _FEATURE_COLUMNS, _ML_AVAILABLE,
            )
            import app.engine.ml_scorer as scorer

assert scorer._ML_AVAILABLE is False, "Model should not be loaded in CI"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DEHRADUN = (30.3165, 78.0322)   # ambulance origin for most tests
ROORKEE  = (29.8543, 77.8880)   # ~52 km from Dehradun

FULL_EQUIP = ["ventilator", "defibrillator", "ct_scan", "blood_bank", "icu"]
CARDIAC_EQUIP = ["ventilator", "defibrillator"]


def make_hospital(
    *,
    lat=30.32, lon=78.04,       # 1 km from DEHRADUN
    beds=20, icu=10,
    equipment=None,
    accepting=True,
    specialist_count=0,
    name="Test Hospital",
    id=1,
):
    return {
        "id": id,
        "name": name,
        "latitude": lat,
        "longitude": lon,
        "available_beds": beds,
        "icu_beds": icu,
        "equipment": equipment if equipment is not None else list(FULL_EQUIP),
        "accepting": accepting,
        "specialist_count": specialist_count,
    }


# ---------------------------------------------------------------------------
# 1. Normalisation helpers
# ---------------------------------------------------------------------------

class TestNormalizeDistance:
    def test_zero_distance_is_one(self):
        assert scorer.normalize_distance(0) == 1.0

    def test_large_distance_approaches_zero(self):
        assert scorer.normalize_distance(1_000_000) == pytest.approx(0.0, abs=1e-5)

    def test_monotone_decreasing(self):
        scores = [scorer.normalize_distance(d) for d in [0, 5, 10, 20, 50]]
        assert scores == sorted(scores, reverse=True)

    def test_10km_value(self):
        # 1/(1 + 10*0.1) = 1/2 = 0.5
        assert scorer.normalize_distance(10) == pytest.approx(0.5)


class TestLogNormalizeBeds:
    def test_zero_beds_is_zero(self):
        assert scorer.log_normalize_beds(0) == 0.0

    def test_max_beds_is_one(self):
        assert scorer.log_normalize_beds(502) == pytest.approx(1.0)

    def test_monotone_increasing(self):
        scores = [scorer.log_normalize_beds(b) for b in [0, 10, 50, 200, 502]]
        assert scores == sorted(scores)

    def test_mid_range_in_bounds(self):
        v = scorer.log_normalize_beds(100)
        assert 0.0 < v < 1.0


class TestNormalizeIcu:
    def test_zero_is_zero(self):
        assert scorer.normalize_icu(0) == 0.0

    def test_at_cap_is_one(self):
        assert scorer.normalize_icu(50) == 1.0

    def test_above_cap_clamped(self):
        assert scorer.normalize_icu(200) == 1.0

    def test_linear_below_cap(self):
        assert scorer.normalize_icu(25) == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# 2. Haversine distance
# ---------------------------------------------------------------------------

class TestHaversineKm:
    def test_same_point_is_zero(self):
        lat, lon = DEHRADUN
        assert scorer.haversine_km(lat, lon, lat, lon) == pytest.approx(0.0, abs=1e-6)

    def test_dehradun_to_roorkee_approx(self):
        # Real road distance is ~58 km; straight-line haversine ~52 km
        km = scorer.haversine_km(*DEHRADUN, *ROORKEE)
        assert 45 < km < 60, f"Unexpected distance: {km:.1f} km"

    def test_symmetry(self):
        d1 = scorer.haversine_km(*DEHRADUN, *ROORKEE)
        d2 = scorer.haversine_km(*ROORKEE, *DEHRADUN)
        assert d1 == pytest.approx(d2)

    def test_positive(self):
        assert scorer.haversine_km(*DEHRADUN, *ROORKEE) > 0


# ---------------------------------------------------------------------------
# 3. Feature vector
# ---------------------------------------------------------------------------

class TestBuildFeatureVector:
    def _fv(self, **kwargs):
        defaults = dict(
            distance_km=10.0, available_beds=20, icu_beds=8,
            hospital_equipment=list(FULL_EQUIP),
            required_equipment=["ventilator", "ct_scan"],
            condition="heart_attack", accepting=True, specialist_count=1,
        )
        defaults.update(kwargs)
        return scorer._build_feature_vector(**defaults)

    def test_length_matches_feature_columns(self):
        assert len(self._fv()) == len(scorer._FEATURE_COLUMNS)

    def test_all_values_in_unit_range(self):
        # condition_severity is 1-3, not 0-1, so exclude index 13
        fv = self._fv()
        for i, (val, name) in enumerate(zip(fv, scorer._FEATURE_COLUMNS)):
            if name == "condition_severity":
                assert 1 <= val <= 3, f"{name}={val}"
            else:
                assert 0.0 <= val <= 1.0, f"{name}={val} out of [0,1]"

    def test_equipment_flags_binary(self):
        fv = self._fv(hospital_equipment=["ventilator"])
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("has_ventilator")] == 1
        assert fv[col.index("has_ct_scan")] == 0

    def test_no_required_equipment_gives_full_match(self):
        fv = self._fv(required_equipment=[])
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("equipment_match")] == 1.0

    def test_partial_equipment_match_ratio(self):
        # hospital has ventilator only; requires ventilator + ct_scan -> 0.5
        fv = self._fv(
            hospital_equipment=["ventilator"],
            required_equipment=["ventilator", "ct_scan"],
        )
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("equipment_match")] == pytest.approx(0.5)

    def test_accepting_flag(self):
        col = scorer._FEATURE_COLUMNS
        assert self._fv(accepting=True)[col.index("accepting")] == 1
        assert self._fv(accepting=False)[col.index("accepting")] == 0

    def test_specialist_present_binary(self):
        col = scorer._FEATURE_COLUMNS
        assert self._fv(specialist_count=0)[col.index("specialist_present")] == 0
        assert self._fv(specialist_count=3)[col.index("specialist_present")] == 1

    def test_hospital_load_and_ot_always_zero(self):
        fv = self._fv()
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("hospital_load")] == 0
        assert fv[col.index("ot_available")] == 0

    def test_severity_weight_critical(self):
        fv = self._fv(condition="cardiac_arrest")
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("severity_weight")] == pytest.approx(1.0)

    def test_severity_weight_low(self):
        fv = self._fv(condition="fever")
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("severity_weight")] == pytest.approx(1/3, rel=1e-3)

    def test_unknown_condition_defaults_to_severity_1(self):
        fv = self._fv(condition="mystery_illness")
        col = scorer._FEATURE_COLUMNS
        assert fv[col.index("condition_severity")] == 1


# ---------------------------------------------------------------------------
# 4. score_hospital — output contract & fallback path
# ---------------------------------------------------------------------------

class TestScoreHospital:
    def _score(self, **overrides):
        defaults = dict(
            ambulance_lat=DEHRADUN[0], ambulance_lon=DEHRADUN[1],
            hospital_lat=30.32, hospital_lon=78.04,   # ~1 km away
            available_beds=20, icu_beds=10,
            hospital_equipment=list(FULL_EQUIP),
            required_equipment=["ventilator", "ct_scan"],
            condition="heart_attack",
            accepting=True, specialist_count=2,
        )
        defaults.update(overrides)
        return scorer.score_hospital(**defaults)

    # -- Output contract ---------------------------------------------------

    def test_required_keys_present(self):
        r = self._score()
        for key in ("score", "ml_used", "score_breakdown", "explanation", "pros", "cons"):
            assert key in r, f"Missing key: {key}"

    def test_score_in_unit_range(self):
        assert 0.0 <= self._score()["score"] <= 1.0

    def test_ml_used_is_false_without_pickle(self):
        assert self._score()["ml_used"] is False

    def test_score_breakdown_keys(self):
        bd = self._score()["score_breakdown"]
        expected = {
            "distance_km", "distance_score", "bed_score", "icu_score",
            "equipment_match", "condition_severity", "severity_weight",
            "available_beds", "icu_beds", "matched_equipment",
            "missing_equipment", "accepting", "specialist_present",
            "final_score", "ml_used",
        }
        assert expected.issubset(bd.keys())

    def test_explanation_is_non_empty_string(self):
        exp = self._score()["explanation"]
        assert isinstance(exp, str) and len(exp) > 10

    def test_pros_and_cons_are_lists(self):
        r = self._score()
        assert isinstance(r["pros"], list)
        assert isinstance(r["cons"], list)

    # -- Prose content -----------------------------------------------------

    def test_nearby_hospital_in_pros(self):
        pros = self._score()["pros"]
        assert any("km" in p for p in pros), f"No distance in pros: {pros}"

    def test_far_hospital_in_cons(self):
        r = self._score(hospital_lat=28.0, hospital_lon=75.0)  # ~400 km
        cons = r["cons"]
        assert any("far" in c.lower() for c in cons), f"No distance warning in cons: {cons}"

    def test_no_beds_reported_in_cons(self):
        r = self._score(available_beds=0)
        cons = r["cons"]
        assert any("bed" in c.lower() for c in cons)

    def test_missing_equipment_in_cons(self):
        r = self._score(
            hospital_equipment=["ventilator"],
            required_equipment=["ventilator", "ct_scan"],
        )
        cons = r["cons"]
        assert any("missing" in c.lower() for c in cons)

    def test_equipment_match_override_updates_breakdown(self):
        r = self._score(
            hospital_equipment=["ventilator"],
            required_equipment=["ventilator", "ct_scan"],
            equipment_match_override=0.9,
        )
        assert r["score_breakdown"]["equipment_match"] == pytest.approx(0.9, rel=1e-3)

    def test_specialist_on_duty_in_pros(self):
        r = self._score(specialist_count=1)
        assert any("specialist" in p.lower() for p in r["pros"])

    # -- Edge cases --------------------------------------------------------

    def test_zero_beds_zero_icu_no_equipment(self):
        r = self._score(available_beds=0, icu_beds=0,
                        hospital_equipment=[],
                        required_equipment=["ventilator"])
        assert 0.0 <= r["score"] <= 1.0
        assert len(r["cons"]) >= 2   # beds + equipment at minimum

    def test_empty_required_equipment(self):
        r = self._score(required_equipment=[])
        assert r["score_breakdown"]["equipment_match"] == 1.0

    def test_same_location_as_ambulance(self):
        r = self._score(
            hospital_lat=DEHRADUN[0], hospital_lon=DEHRADUN[1]
        )
        assert r["score_breakdown"]["distance_km"] == pytest.approx(0.0, abs=0.1)
        assert any("close" in p.lower() or "km" in p for p in r["pros"])

    def test_not_accepting_does_not_crash(self):
        r = self._score(accepting=False)
        assert "score" in r

    def test_score_breakdown_distance_matches_haversine(self):
        r = self._score()
        expected = scorer.haversine_km(
            DEHRADUN[0], DEHRADUN[1], 30.32, 78.04
        )
        assert r["score_breakdown"]["distance_km"] == pytest.approx(expected, rel=0.01)


# ---------------------------------------------------------------------------
# 5. rank_hospitals — ordering, enrichment, edge cases
# ---------------------------------------------------------------------------

class TestRankHospitals:
    AMBUL = dict(ambulance_lat=DEHRADUN[0], ambulance_lon=DEHRADUN[1])

    async def _rank(self, hospitals, *, required_equipment=None, condition="heart_attack"):
        return await scorer.rank_hospitals(
            hospitals,
            **self.AMBUL,
            required_equipment=required_equipment or ["ventilator"],
            condition=condition,
        )

    # -- Ordering ----------------------------------------------------------

    @pytest.mark.asyncio
    async def test_closer_hospital_ranks_first(self):
        near = make_hospital(lat=30.32, lon=78.04, id=1, name="Near")   # ~1 km
        far  = make_hospital(lat=28.00, lon=75.00, id=2, name="Far")    # ~400 km
        ranked = await self._rank([far, near])
        assert ranked[0]["name"] == "Near"

    @pytest.mark.asyncio
    async def test_better_equipped_hospital_ranks_higher_at_same_distance(self):
        full = make_hospital(lat=30.32, lon=78.04, id=1, name="Full",
                             equipment=["ventilator", "ct_scan", "defibrillator"])
        partial = make_hospital(lat=30.32, lon=78.04, id=2, name="Partial",
                                equipment=[])
        ranked = await self._rank([partial, full], required_equipment=["ventilator", "ct_scan"])
        assert ranked[0]["name"] == "Full"

    @pytest.mark.asyncio
    async def test_rank_uses_prefilter_equipment_match_score_when_provided(self):
        favored = make_hospital(id=1, name="Favored", equipment=[])
        underweighted = make_hospital(id=2, name="Underweighted", equipment=["ventilator", "ct_scan"])
        favored["equipment_match_score"] = 0.95
        underweighted["equipment_match_score"] = 0.20
        ranked = await self._rank([underweighted, favored], required_equipment=["ventilator", "ct_scan"])
        assert ranked[0]["name"] == "Favored"

    @pytest.mark.asyncio
    async def test_sorted_descending_by_score(self):
        hospitals = [make_hospital(id=i, lat=30.3 + i*0.1, lon=78.0) for i in range(5)]
        ranked = await self._rank(hospitals)
        scores = [h["score"] for h in ranked]
        assert scores == sorted(scores, reverse=True)

    # -- Enrichment --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_all_required_keys_present_in_output(self):
        hospitals = [make_hospital()]
        ranked = await self._rank(hospitals)
        h = ranked[0]
        for key in ("score", "ml_used", "score_breakdown", "explanation", "pros", "cons"):
            assert key in h, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_original_hospital_fields_preserved(self):
        h = make_hospital(id=42, name="MyHospital", beds=99)
        ranked = await self._rank([h])
        assert ranked[0]["id"] == 42
        assert ranked[0]["name"] == "MyHospital"
        assert ranked[0]["available_beds"] == 99

    # -- Edge cases --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_empty_list_returns_empty(self):
        assert await self._rank([]) == []

    @pytest.mark.asyncio
    async def test_single_hospital_returned(self):
        ranked = await self._rank([make_hospital()])
        assert len(ranked) == 1

    @pytest.mark.asyncio
    async def test_all_hospitals_scored(self):
        hospitals = [make_hospital(id=i) for i in range(10)]
        ranked = await self._rank(hospitals)
        assert len(ranked) == 10

    @pytest.mark.asyncio
    async def test_missing_optional_keys_use_defaults(self):
        # hospital dict with only the minimum required keys
        minimal = {"id": 1, "name": "Minimal", "latitude": 30.32, "longitude": 78.04}
        ranked = await self._rank([minimal])
        assert 0.0 <= ranked[0]["score"] <= 1.0

    @pytest.mark.asyncio
    async def test_all_identical_hospitals_all_returned(self):
        hospitals = [make_hospital(id=i) for i in range(5)]
        ranked = await self._rank(hospitals)
        assert len(ranked) == 5


# ---------------------------------------------------------------------------
# 6. Weighted fallback — formula correctness without ML model
# ---------------------------------------------------------------------------

class TestWeightedFallback:
    """
    Tests the _weighted_score function directly.
    These implicitly run when _ML_AVAILABLE is False, which is the case
    for the entire suite (CI environment without the pickle).
    """

    def test_perfect_candidate_scores_high(self):
        score = scorer._weighted_score(
            distance_km=0.5, available_beds=100, icu_beds=50,
            hospital_equipment=list(FULL_EQUIP),
            required_equipment=["ventilator"],
            condition="cardiac_arrest",
        )
        assert score > 0.7, f"Expected high score, got {score:.4f}"

    def test_terrible_candidate_scores_low(self):
        score = scorer._weighted_score(
            distance_km=200, available_beds=0, icu_beds=0,
            hospital_equipment=[],
            required_equipment=["ventilator", "ct_scan"],
            condition="fever",
        )
        assert score < 0.3, f"Expected low score, got {score:.4f}"

    def test_weights_sum_effect_distance_dominant(self):
        # Two identical hospitals where distance is the only variable
        score_near = scorer._weighted_score(2,  20, 10, ["ventilator"], ["ventilator"], "fever")
        score_far  = scorer._weighted_score(50, 20, 10, ["ventilator"], ["ventilator"], "fever")
        assert score_near > score_far, (
            f"Near hospital ({score_near:.3f}) should beat identical-but-distant one ({score_far:.3f})"
        )

    def test_output_in_unit_range(self):
        for km in [0, 1, 10, 50, 200]:
            score = scorer._weighted_score(km, 10, 5, ["ventilator"], ["ventilator"], "stroke")
            assert 0.0 <= score <= 1.0, f"Score {score} out of range at {km} km"


# ---------------------------------------------------------------------------
# 7. CONDITION_SEVERITY_MAP completeness
# ---------------------------------------------------------------------------

class TestConditionSeverityMap:
    EXPECTED_CONDITIONS = {
        "minor_injury", "fever", "fracture",
        "stroke", "heart_attack", "respiratory_distress", "severe_bleeding",
        "cardiac_arrest", "multi_trauma", "head_injury", "poisoning",
    }

    def test_all_expected_conditions_present(self):
        missing = self.EXPECTED_CONDITIONS - set(scorer.CONDITION_SEVERITY_MAP.keys())
        assert not missing, f"Missing conditions: {missing}"

    def test_severity_values_are_1_2_or_3(self):
        for cond, sev in scorer.CONDITION_SEVERITY_MAP.items():
            assert sev in (1, 2, 3), f"{cond} has unexpected severity {sev}"

    def test_critical_conditions_are_severity_3(self):
        for cond in ("cardiac_arrest", "multi_trauma", "head_injury", "poisoning"):
            assert scorer.CONDITION_SEVERITY_MAP[cond] == 3

    def test_moderate_conditions_are_severity_2(self):
        for cond in ("stroke", "heart_attack", "respiratory_distress", "severe_bleeding"):
            assert scorer.CONDITION_SEVERITY_MAP[cond] == 2

    def test_low_conditions_are_severity_1(self):
        for cond in ("minor_injury", "fever", "fracture"):
            assert scorer.CONDITION_SEVERITY_MAP[cond] == 1


# ---------------------------------------------------------------------------
# 8. ML path — mock model smoke test
# ---------------------------------------------------------------------------

class TestMlPath:
    """
    Injects a mock sklearn-like model to verify the ML code path
    without needing the actual pickle file.
    """

    def test_predict_proba_result_used_as_score(self, monkeypatch):
        import numpy as np

        class MockModel:
            def predict_proba(self, X):
                # Always return 0.87 confidence for positive class
                return np.array([[0.13, 0.87]])

        monkeypatch.setattr(scorer, "_ml_model", MockModel())
        monkeypatch.setattr(scorer, "_ML_AVAILABLE", True)

        r = scorer.score_hospital(
            ambulance_lat=DEHRADUN[0], ambulance_lon=DEHRADUN[1],
            hospital_lat=30.32, hospital_lon=78.04,
            available_beds=20, icu_beds=5,
            hospital_equipment=["ventilator"],
            required_equipment=["ventilator"],
            condition="stroke",
        )
        assert r["ml_used"] is True
        # Raw ML probability preserved in ml_score
        assert r["ml_score"] == pytest.approx(0.87, rel=1e-2)
        # Calibrated confidence: raw 0.87 is 6.96× pool baseline (0.125),
        # tanh rescale saturates → clamped to 1.0
        calibrated = r["score_breakdown"]["ml_confidence"]
        assert calibrated == pytest.approx(1.0, abs=0.01)
        # score is now blended: interpretable_score + (calibrated - 0.5) * 0.24
        # It should be higher than raw ML when rule-based score is high,
        # and always in valid range
        assert 0.15 <= r["score"] <= 1.0
        interpretable = r["score_breakdown"]["interpretable_score"]
        expected_blended = min(1.0, max(0.15, interpretable + (calibrated - 0.5) * 0.24))
        assert r["score"] == pytest.approx(expected_blended, rel=0.05)

    def test_ml_failure_falls_back_to_weighted(self, monkeypatch):
        class BrokenModel:
            def predict_proba(self, X):
                raise RuntimeError("simulated sklearn version mismatch")

        monkeypatch.setattr(scorer, "_ml_model", BrokenModel())
        monkeypatch.setattr(scorer, "_ML_AVAILABLE", True)

        r = scorer.score_hospital(
            ambulance_lat=DEHRADUN[0], ambulance_lon=DEHRADUN[1],
            hospital_lat=30.32, hospital_lon=78.04,
            available_beds=20, icu_beds=5,
            hospital_equipment=["ventilator"],
            required_equipment=["ventilator"],
            condition="stroke",
        )
        assert r["ml_used"] is False
        assert 0.0 <= r["score"] <= 1.0
        assert "ml_confidence" not in r["score_breakdown"]

    def test_trained_model_smoke_has_predict_interfaces(self):
        model_path = Path(__file__).resolve().parent.parent / "ml_training" / "hospital_model.pkl"
        model = scorer._extract_model(joblib.load(model_path))
        assert hasattr(model, "predict") and hasattr(model, "predict_proba")
