"""
test_ml_scorer.py

Tests for the new transparent weighted scorer (ml_scorer.py).
Replaces the previous tests that covered the RandomForest predictor.

Run with:
    cd backend
    python -m pytest tests/test_ml_scorer.py -v
"""
import math
import pytest

from app.engine.ml_scorer import (
    CONDITION_SPECIALIST_MAP,
    SEVERITY_MAP,
    ScoredHospital,
    _beds_score,
    _distance_score,
    _eta,
    _haversine,
    _specialist_score,
    score_hospitals,
)
from app.core.severity import Severity


# ── Fixtures ─────────────────────────────────────────────────────────────────

def make_hospital(
    id_: int = 1,
    name: str = "General Hospital",
    lat: float = 28.65,
    lng: float = 77.23,
    beds: int = 10,
    equipment: list[str] | None = None,
    specialists: list[str] | None = None,
) -> dict:
    return {
        "id": id_,
        "name": name,
        "latitude": lat,
        "longitude": lng,
        "available_beds": beds,
        "equipment": equipment or [],
        "specialists": specialists or [],
        "data_source": "live",
        "last_updated": None,
        "address": f"Hospital {id_} Address",
    }


AMB_LAT, AMB_LNG = 28.61, 77.21  # Ambulance position (New Delhi area)


# ── Haversine ─────────────────────────────────────────────────────────────────

class TestHaversine:
    def test_zero_distance(self):
        assert _haversine(28.0, 77.0, 28.0, 77.0) == pytest.approx(0.0, abs=1e-6)

    def test_known_distance(self):
        # Delhi (28.6139, 77.2090) to Agra (27.1767, 78.0081) ≈ 178 km
        d = _haversine(28.6139, 77.2090, 27.1767, 78.0081)
        assert 170 < d < 190

    def test_symmetry(self):
        d1 = _haversine(28.0, 77.0, 29.0, 78.0)
        d2 = _haversine(29.0, 78.0, 28.0, 77.0)
        assert d1 == pytest.approx(d2, rel=1e-6)

    def test_returns_float(self):
        assert isinstance(_haversine(0, 0, 1, 1), float)


# ── Sub-score functions ───────────────────────────────────────────────────────

class TestDistanceScore:
    def test_zero_distance_is_perfect(self):
        assert _distance_score(0.0, 60) == pytest.approx(1.0)

    def test_at_max_is_zero(self):
        assert _distance_score(60.0, 60) == pytest.approx(0.0)

    def test_beyond_max_clamped_to_zero(self):
        assert _distance_score(100.0, 60) == 0.0

    def test_exponential_decay(self):
        # 30 is midpoint of 60, normalized is 0.5, exp(-3 * 0.5) = 0.223
        assert _distance_score(30.0, 60) == pytest.approx(math.exp(-1.5), abs=0.01)


class TestBedsScore:
    def test_zero_beds(self):
        assert _beds_score(0) == 0.0

    def test_at_cap(self):
        assert _beds_score(50) == pytest.approx(1.0)

    def test_beyond_cap_clamped(self):
        assert _beds_score(100) == pytest.approx(1.0)

    def test_proportional(self):
        assert _beds_score(25) == pytest.approx(0.5)

    def test_icu_bonus_critical(self):
        # 10 beds -> 0.2 base
        # 2 ICU beds -> 2 * 0.15 = 0.3 bonus
        # Total = 0.5
        assert _beds_score(10, icu_beds=2, severity=Severity.CRITICAL) == pytest.approx(0.5)


class TestSpecialistScore:
    def test_no_requirements_uses_doctor_count(self):
        # With 1 specialist, ratio is 1/20 = 0.05
        assert _specialist_score(["cardiologist"], []) == pytest.approx(0.05)

    def test_full_match(self):
        assert _specialist_score(
            ["cardiologist", "neurologist"],
            ["cardiologist", "neurologist"],
        ) == pytest.approx(1.0)

    def test_partial_match(self):
        score = _specialist_score(
            ["cardiologist"],
            ["cardiologist", "neurologist"],
        )
        assert score == pytest.approx(0.5)

    def test_no_match(self):
        assert _specialist_score(["radiologist"], ["cardiologist"]) == pytest.approx(0.0)

    def test_case_insensitive(self):
        assert _specialist_score(["CARDIOLOGIST"], ["cardiologist"]) == pytest.approx(1.0)


# ── ETA ──────────────────────────────────────────────────────────────────────

class TestEta:
    def test_minimum_one_minute(self):
        assert _eta(0.1) == 1

    def test_10km_at_40kmh(self):
        assert _eta(10.0) == 15   # 10/40 * 60 = 15

    def test_returns_int(self):
        assert isinstance(_eta(5.0), int)


# ── score_hospitals — hard filter ─────────────────────────────────────────────

class TestScoreHospitalsHardFilter:
    def test_rejects_hospital_missing_any_equipment(self):
        h = make_hospital(
            id_=1,
            lat=AMB_LAT + 0.05,
            lng=AMB_LNG,
            beds=10,
            equipment=["defibrillator"],  # missing "ventilator"
        )
        ranked, summary = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator", "ventilator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert ranked == []
        assert summary["missing_equipment"] == 1

    def test_accepts_hospital_with_all_equipment(self):
        h = make_hospital(
            id_=1,
            lat=AMB_LAT + 0.05,
            lng=AMB_LNG,
            beds=10,
            equipment=["defibrillator", "ventilator"],
        )
        ranked, summary = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator", "ventilator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert len(ranked) == 1
        assert summary["missing_equipment"] == 0

    def test_equipment_filter_is_case_insensitive(self):
        h = make_hospital(
            equipment=["Defibrillator", "VENTILATOR"],
            beds=5,
            lat=AMB_LAT + 0.05,
            lng=AMB_LNG,
        )
        ranked, _ = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator", "ventilator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert len(ranked) == 1

    def test_rejects_hospital_with_insufficient_beds_critical(self):
        h = make_hospital(
            equipment=["defibrillator"],
            beds=0,
            lat=AMB_LAT + 0.01,
            lng=AMB_LNG,
        )
        ranked, summary = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
            severity_override="critical",
        )
        assert ranked == []
        assert summary["insufficient_beds"] == 1

    def test_no_match_returns_empty_list(self):
        h = make_hospital(equipment=[], beds=0, lat=AMB_LAT + 5, lng=AMB_LNG)
        ranked, summary = score_hospitals(
            hospitals=[h],
            condition="trauma",
            required_equipment=["blood_bank", "icu"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert ranked == []
        assert summary["total_rejected"] >= 1


# ── score_hospitals — ranking ─────────────────────────────────────────────────

class TestScoreHospitalsRanking:
    def _two_hospitals(self):
        """Close hospital with fewer beds vs far hospital with more beds."""
        close = make_hospital(
            id_=1, name="Close", lat=AMB_LAT + 0.05, lng=AMB_LNG,
            beds=5, equipment=["defibrillator"],
        )
        far = make_hospital(
            id_=2, name="Far", lat=AMB_LAT + 0.5, lng=AMB_LNG,
            beds=40, equipment=["defibrillator"],
        )
        return [close, far]

    def test_returns_top_3_max(self):
        hospitals = [
            make_hospital(id_=i, lat=AMB_LAT + i * 0.05, lng=AMB_LNG,
                          beds=10, equipment=["defib"])
            for i in range(1, 7)
        ]
        ranked, _ = score_hospitals(
            hospitals=hospitals,
            condition="cardiac arrest",
            required_equipment=["defib"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert len(ranked) <= 3

    def test_critical_prefers_closer_hospital(self):
        ranked, _ = score_hospitals(
            hospitals=self._two_hospitals(),
            condition="cardiac arrest",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
            severity_override="critical",
        )
        assert ranked[0].name == "Close"

    def test_low_severity_may_prefer_more_beds(self):
        ranked, _ = score_hospitals(
            hospitals=self._two_hospitals(),
            condition="psychiatric",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
            severity_override="low",
        )
        assert len(ranked) >= 1

    def test_scores_are_descending(self):
        hospitals = [
            make_hospital(id_=i, lat=AMB_LAT + i * 0.1, lng=AMB_LNG,
                          beds=10, equipment=["defib"])
            for i in range(1, 5)
        ]
        ranked, _ = score_hospitals(
            hospitals=hospitals,
            condition="cardiac arrest",
            required_equipment=["defib"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        scores = [h.score for h in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_score_breakdown_keys(self):
        h = make_hospital(
            lat=AMB_LAT + 0.05, lng=AMB_LNG, beds=10,
            equipment=["defibrillator"],
        )
        ranked, _ = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert set(ranked[0].score_breakdown.keys()) == {
            "distance", "beds", "specialist", "equipment", "outcome"
        }

    def test_equipment_sub_score_richness(self):
        h = make_hospital(
            lat=AMB_LAT + 0.05, lng=AMB_LNG, beds=10,
            equipment=["defibrillator", "oxygen", "ecg"],
        )
        ranked, _ = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        # Base 0.6 + (0.1 * 3 bonus items from mapping) = 0.9
        assert ranked[0].score_breakdown["equipment"] == pytest.approx(0.9)

    def test_composite_score_bounds(self):
        h = make_hospital(
            lat=AMB_LAT + 0.05, lng=AMB_LNG, beds=10,
            equipment=["defibrillator"],
        )
        ranked, _ = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert 0.0 <= ranked[0].score <= 1.0


# ── score_hospitals — explanation/pros/cons ───────────────────────────────────

class TestScoreHospitalsExplanation:
    def _rank_one(self):
        h = make_hospital(
            lat=AMB_LAT + 0.05, lng=AMB_LNG, beds=15,
            equipment=["defibrillator"],
            specialists=["cardiologist"],
        )
        ranked, _ = score_hospitals(
            hospitals=[h],
            condition="cardiac arrest",
            required_equipment=["defibrillator"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        return ranked[0]

    def test_explanation_is_list_of_strings(self):
        r = self._rank_one()
        assert isinstance(r.explanation, list)
        assert all(isinstance(s, str) for s in r.explanation)
        assert len(r.explanation) >= 1

    def test_pros_not_empty(self):
        r = self._rank_one()
        assert len(r.pros) >= 1

    def test_cons_not_empty(self):
        r = self._rank_one()
        assert len(r.cons) >= 1

    def test_eta_minutes_populated(self):
        r = self._rank_one()
        assert r.eta_minutes is not None
        assert r.eta_minutes >= 1


# ── Severity/condition maps ──────

class TestSeverityMapping:
    def test_cardiac_arrest_is_critical(self):
        assert SEVERITY_MAP["cardiac arrest"] == Severity.CRITICAL

    def test_psychiatric_is_low(self):
        assert SEVERITY_MAP["psychiatric"] == Severity.LOW

    def test_burns_is_moderate(self):
        assert SEVERITY_MAP["burns"] == Severity.MODERATE


class TestSpecialistMapping:
    def test_cardiac_arrest_has_cardiologist(self):
        assert "cardiologist" in CONDITION_SPECIALIST_MAP["cardiac arrest"]

    def test_stroke_has_neurologist(self):
        assert "neurologist" in CONDITION_SPECIALIST_MAP["stroke"]

    def test_unknown_condition_returns_empty_list_from_scorer(self):
        h = make_hospital(
            lat=AMB_LAT + 0.05, lng=AMB_LNG, beds=10,
            equipment=["defib"],
        )
        ranked, _ = score_hospitals(
            hospitals=[h],
            condition="unknown_rare_condition",
            required_equipment=["defib"],
            ambulance_lat=AMB_LAT,
            ambulance_lng=AMB_LNG,
        )
        assert isinstance(ranked, list)
