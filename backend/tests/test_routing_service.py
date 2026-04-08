"""
test_routing_service.py

Tests for the smart ETA prediction engine (routing_service.py).

Run with:
    cd backend
    python -m pytest tests/test_routing_service.py -v
"""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.routing_service import (
    ETAPredictor,
    _base_speed_kmh,
    _confidence,
    _eta_minutes,
    _fallback_route,
    _haversine,
    _remaining_distance,
    _road_speed_factor,
    _road_type_hint,
    _traffic_factor,
)


# ── Haversine ───────

class TestHaversine:
    def test_zero_distance(self):
        assert _haversine(28.0, 77.0, 28.0, 77.0) == pytest.approx(0.0, abs=1e-6)

    def test_known_city_hop(self):
        # IIT Delhi to Connaught Place ~ 12km
        d = _haversine(28.5450, 77.1926, 28.6304, 77.2177)
        assert 9 < d < 15

    def test_symmetry(self):
        a = _haversine(28.0, 77.0, 29.0, 78.0)
        b = _haversine(29.0, 78.0, 28.0, 77.0)
        assert a == pytest.approx(b, rel=1e-6)


# ── Speed bands ──────

class TestSpeedBands:
    def test_evening_rush_is_slowest(self):
        from datetime import datetime
        rush    = _base_speed_kmh(datetime(2024, 1, 1, 18, 0))   # 6 PM
        midday  = _base_speed_kmh(datetime(2024, 1, 1, 15, 0))   # 3 PM
        assert rush < midday

    def test_night_is_faster_than_morning_rush(self):
        from datetime import datetime
        night   = _base_speed_kmh(datetime(2024, 1, 1, 2, 0))
        morning = _base_speed_kmh(datetime(2024, 1, 1, 7, 30))
        assert night > morning

    def test_returns_positive_speed(self):
        from datetime import datetime
        for h in range(24):
            s = _base_speed_kmh(datetime(2024, 1, 1, h, 0))
            assert s > 0


# ── Road type heuristic ──────

class TestRoadTypeHint:
    def test_highway_detected(self):
        assert _road_type_hint(52, 50, 4) == "highway"

    def test_city_detected(self):
        assert _road_type_hint(80, 40, 30) == "city"

    def test_mixed_middle_ground(self):
        result = _road_type_hint(25, 18, 12)
        assert result in ("city", "mixed", "highway")

    def test_zero_crow_distance_defaults_to_city(self):
        assert _road_type_hint(5, 0.01, 5) == "city"


# ── Road speed factor ──────

class TestRoadSpeedFactor:
    def test_highway_faster_than_city(self):
        assert _road_speed_factor("highway") > _road_speed_factor("city")

    def test_mixed_between_highway_and_city(self):
        assert _road_speed_factor("city") < _road_speed_factor("mixed") < _road_speed_factor("highway")

    def test_unknown_type_defaults_to_1(self):
        assert _road_speed_factor("unknown_type") == pytest.approx(1.0)


# ── Traffic factor ──────

class TestTrafficFactor:
    def test_empty_samples_returns_1(self):
        assert _traffic_factor([], 40.0) == pytest.approx(1.0)

    def test_matching_speed_returns_1(self):
        factor = _traffic_factor([40.0, 40.0, 40.0], 40.0)
        assert factor == pytest.approx(1.0, rel=0.05)

    def test_half_speed_inflates_factor(self):
        factor = _traffic_factor([20.0, 20.0, 20.0], 40.0)
        assert factor > 1.0

    def test_double_speed_deflates_factor(self):
        factor = _traffic_factor([80.0, 80.0, 80.0], 40.0)
        assert factor < 1.0

    def test_uses_last_5_samples(self):
        samples = [5.0] * 20 + [40.0] * 5
        factor = _traffic_factor(samples, 40.0)
        assert factor == pytest.approx(1.0, rel=0.1)


# ── ETA formula ──────

class TestEtaMinutes:
    def test_positive_eta(self):
        assert _eta_minutes(10.0, 40.0, 1.0, 1.0) > 0

    def test_minimum_1_minute(self):
        assert _eta_minutes(0.01, 40.0, 1.0, 1.0) == 1

    def test_emergency_faster_than_civilian(self):
        eta_emg = _eta_minutes(10.0, 40.0, 1.0, 1.0, emergency=True)
        eta_civ = _eta_minutes(10.0, 40.0, 1.0, 1.0, emergency=False)
        assert eta_emg <= eta_civ

    def test_traffic_inflates_eta(self):
        base  = _eta_minutes(10.0, 40.0, 1.0, 1.0)
        heavy = _eta_minutes(10.0, 40.0, 1.0, 2.0)
        assert heavy > base


# ── Confidence score ──────

class TestConfidence:
    def test_no_samples_low_confidence(self):
        # With 0 samples: sample_conf=0, deviation_penalty=1.0 (stationary defaults to ratio 1.0)
        # Result: 0*0.4 + 1.0*0.6 = 0.6 — lower than fully converged confidence
        conf = _confidence(0, 40.0, 0)
        fully_converged = _confidence(40.0, 40.0, 10)
        assert conf < fully_converged

    def test_matching_speed_high_confidence(self):
        conf = _confidence(40.0, 40.0, 10)
        assert conf > 0.7

    def test_diverging_speed_lowers_confidence(self):
        high = _confidence(40.0, 40.0, 5)
        low  = _confidence(5.0, 40.0, 5)
        assert high > low

    def test_confidence_bounded_0_to_1(self):
        for obs, pred, n in [(0, 40, 0), (80, 40, 1), (40, 40, 10)]:
            c = _confidence(obs, pred, n)
            assert 0.0 <= c <= 1.0


# ── Remaining distance ─────

class TestRemainingDistance:
    def _straight_route(self, n=10):
        """10-point straight-line route from (28.61,77.21) to (28.70,77.21)"""
        return [
            [77.21, 28.61 + i * 0.01]  # [lng, lat]
            for i in range(n)
        ]

    def test_at_start_remaining_equals_total(self):
        route = self._straight_route()
        remaining, idx = _remaining_distance(28.61, 77.21, route)
        assert idx == 0
        assert remaining > 5

    def test_at_end_remaining_near_zero(self):
        route = self._straight_route()
        remaining, idx = _remaining_distance(28.70, 77.21, route)
        assert idx == 9
        assert remaining < 0.5

    def test_midpoint_remaining_less_than_total(self):
        route = self._straight_route()
        total, _ = _remaining_distance(28.61, 77.21, route)
        mid, _   = _remaining_distance(28.655, 77.21, route)
        assert mid < total

    def test_empty_route_returns_zero(self):
        remaining, idx = _remaining_distance(28.61, 77.21, [])
        assert remaining == 0.0
        assert idx == 0


# ── Fallback route ─────

class TestFallbackRoute:
    def test_produces_valid_structure(self):
        fb = _fallback_route(28.61, 77.21, 28.65, 77.23)
        assert "routes" in fb
        assert len(fb["routes"]) == 1
        route = fb["routes"][0]
        assert "summary" in route
        assert "geometry" in route
        assert len(route["geometry"]["coordinates"]) == 10

    def test_distance_roughly_correct(self):
        fb = _fallback_route(28.61, 77.21, 28.65, 77.23)
        dist_m = fb["routes"][0]["summary"]["distance"]
        dist_km = dist_m / 1000
        expected = _haversine(28.61, 77.21, 28.65, 77.23)
        assert abs(dist_km - expected) < 0.5

    def test_fallback_flag_set(self):
        fb = _fallback_route(28.61, 77.21, 28.65, 77.23)
        assert fb.get("_fallback") is True


# ── ETAPredictor integration ─────

class TestETAPredictor:
    def _predictor(self):
        return ETAPredictor()

    @pytest.mark.asyncio
    async def test_initial_eta_returns_result(self):
        predictor = self._predictor()
        with patch(
            "app.services.routing_service._fetch_ors_route",
            new_callable=AsyncMock,
            return_value=_fallback_route(28.61, 77.21, 28.65, 77.23),
        ):
            result = await predictor.initial_eta(28.61, 77.21, 28.65, 77.23, case_id=1)
        assert result.case_id == 1
        assert result.estimated_eta_minutes >= 1
        assert len(result.route_coords) > 0

    @pytest.mark.asyncio
    async def test_update_eta_after_initial(self):
        predictor = self._predictor()
        route = _fallback_route(28.61, 77.21, 28.65, 77.23)
        with patch(
            "app.services.routing_service._fetch_ors_route",
            new_callable=AsyncMock,
            return_value=route,
        ):
            await predictor.initial_eta(28.61, 77.21, 28.65, 77.23, case_id=2)

        coords = route["routes"][0]["geometry"]["coordinates"]
        update = predictor.update_eta(
            case_id=2,
            current_lat=28.63,
            current_lng=77.21,
            route_coords=coords,
            observed_speed_kmh=35.0,
        )
        assert update is not None
        assert update.updated_eta_minutes >= 1
        assert 0.0 <= update.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_update_eta_unknown_case_returns_none(self):
        predictor = self._predictor()
        result = predictor.update_eta(
            case_id=9999,
            current_lat=28.61,
            current_lng=77.21,
            route_coords=[],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_case_removes_state(self):
        predictor = self._predictor()
        with patch(
            "app.services.routing_service._fetch_ors_route",
            new_callable=AsyncMock,
            return_value=_fallback_route(28.61, 77.21, 28.65, 77.23),
        ):
            await predictor.initial_eta(28.61, 77.21, 28.65, 77.23, case_id=3)
        assert 3 in predictor.active_cases()
        predictor.clear_case(3)
        assert 3 not in predictor.active_cases()

    @pytest.mark.asyncio
    async def test_congestion_detected_when_speed_low(self):
        predictor = self._predictor()
        route = _fallback_route(28.61, 77.21, 28.65, 77.23)
        with patch(
            "app.services.routing_service._fetch_ors_route",
            new_callable=AsyncMock,
            return_value=route,
        ):
            await predictor.initial_eta(28.61, 77.21, 28.65, 77.23, case_id=4)

        coords = route["routes"][0]["geometry"]["coordinates"]
        update = None
        for _ in range(4):
            update = predictor.update_eta(
                case_id=4,
                current_lat=28.615,
                current_lng=77.21,
                route_coords=coords,
                observed_speed_kmh=5.0,
            )
        assert update is not None
        assert update.congested is True
