"""
routing_service.py — Smart ETA prediction engine.

Replaces the naive `distance / 40 km/h` formula with a weighted model
that accounts for:

  1. Route geometry    — actual road distance from ORS (not crow-flies)
  2. Time-of-day speed — rush hour / night / midday bands
  3. Road type weight  — highway vs city vs residential estimated from
                         step count and distance ratio
  4. Traffic factor    — recalculated on every GPS ping using recent
                         observed speed vs predicted speed
  5. Emergency bonus   — lights-and-siren mode reduces effective travel
                         time (ambulances can legally beat traffic)

The result is an ETA that self-corrects as the ambulance moves:
if the driver is going faster than predicted, the ETA tightens;
if they hit a jam, it loosens — exactly like Swiggy.

Usage:
    from app.services.routing_service import eta_predictor
    result = await eta_predictor.initial_eta(...)
    update = eta_predictor.update_eta(...)
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import httpx

# ── ORS config ────────────────────────────────────────────────────────────────
ORS_BASE_URL = "https://api.openrouteservice.org/v2/directions/driving-car"
ORS_API_KEY = os.getenv("ORS_API_KEY", "")

# ── Speed bands (km/h) — tuned for Indian urban/suburban conditions ───────────
# Each band: (start_hour, end_hour, base_speed_kmh)
_SPEED_BANDS = [
    (0,  6,  55),   # night — clear roads
    (6,  9,  28),   # morning rush
    (9,  12, 42),   # mid-morning
    (12, 14, 38),   # lunch hour
    (14, 17, 44),   # afternoon
    (17, 20, 26),   # evening rush — worst
    (20, 23, 48),   # evening clear-up
    (23, 24, 54),   # late night
]

# Emergency lights reduce effective time by this factor
_EMERGENCY_BONUS = 0.82   # ambulances ~18% faster than civilian estimate

# Confidence decay: if observed speed < X% of predicted, flag congestion
_CONGESTION_THRESHOLD = 0.65


# ── Data structures ───

@dataclass
class RouteResult:
    """Output of initial_eta() — full route info."""
    case_id: int
    route_coords: list[list[float]]     # [[lng, lat], ...] — ORS format
    total_distance_km: float
    estimated_eta_minutes: int
    confidence: float                   # 0.0–1.0
    speed_used_kmh: float
    road_type_hint: str                 # "highway" | "city" | "mixed"
    traffic_factor: float               # multiplier applied to base ETA
    fetched_at: float                   # unix timestamp


@dataclass
class ETAUpdate:
    """Output of update_eta() — live recalculation after a GPS ping."""
    case_id: int
    remaining_distance_km: float
    updated_eta_minutes: int
    delta_minutes: int                  # positive = slower, negative = faster
    confidence: float
    observed_speed_kmh: float
    predicted_speed_kmh: float
    congested: bool
    recalculated_at: float


@dataclass
class _CaseState:
    """Internal state kept per active case."""
    initial_distance_km: float
    initial_eta_minutes: int
    last_eta_minutes: int
    last_lat: float
    last_lng: float
    last_ping_time: float
    speed_samples: list[float] = field(default_factory=list)


# ── Helpers ──────

def _base_speed_kmh(at: Optional[datetime] = None) -> float:
    """Return time-of-day speed estimate."""
    hour = (at or datetime.now()).hour
    for start, end, speed in _SPEED_BANDS:
        if start <= hour < end:
            return float(speed)
    return 40.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _road_type_hint(route_distance_km: float, crow_distance_km: float, step_count: int) -> str:
    """
    Heuristic: ratio of road distance to straight-line distance.
    Low ratio + few steps → likely highway.
    High ratio + many steps → city grid.
    """
    if crow_distance_km < 0.1:
        return "city"
    ratio = route_distance_km / crow_distance_km
    if ratio < 1.25 and step_count < 8:
        return "highway"
    if ratio > 1.6 or step_count > 20:
        return "city"
    return "mixed"


def _road_speed_factor(road_type: str) -> float:
    return {"highway": 1.30, "mixed": 1.00, "city": 0.78}.get(road_type, 1.0)


def _traffic_factor(speed_samples: list[float], predicted_speed: float) -> float:
    """
    Compare recent observed speed to predicted.
    Returns a multiplier > 1.0 when traffic is heavy (slower → longer ETA).
    """
    if not speed_samples:
        return 1.0
    avg_observed = sum(speed_samples[-5:]) / len(speed_samples[-5:])
    if avg_observed < 1.0:   # ambulance stationary (scene, traffic light)
        return 1.0
    ratio = avg_observed / max(predicted_speed, 1.0)
    ratio = max(0.3, min(ratio, 2.0))
    # Invert: if going slower than predicted, ETA multiplier is > 1
    return max(0.5, 1.0 / ratio)


def _eta_minutes(
    distance_km: float,
    base_speed: float,
    road_factor: float,
    traffic_factor: float,
    emergency: bool = True,
) -> int:
    effective_speed = base_speed * road_factor
    if emergency:
        effective_speed /= _EMERGENCY_BONUS   # divide to get higher speed = lower ETA
    travel_hours = distance_km / max(effective_speed, 1.0)
    raw_minutes = travel_hours * 60 * traffic_factor
    return max(1, round(raw_minutes))


def _remaining_distance(
    current_lat: float,
    current_lng: float,
    route_coords: list[list[float]],
) -> tuple[float, int]:
    """
    Find the closest route point to current position, return
    (remaining_km, nearest_index).
    ORS coords are [lng, lat].
    """
    if not route_coords:
        return 0.0, 0

    min_dist = float("inf")
    nearest_idx = 0
    for i, (lng, lat) in enumerate(route_coords):
        d = _haversine(current_lat, current_lng, lat, lng)
        if d < min_dist:
            min_dist = d
            nearest_idx = i

    # Sum distances from nearest_idx to end of route
    remaining_km = 0.0
    for i in range(nearest_idx, len(route_coords) - 1):
        lng1, lat1 = route_coords[i]
        lng2, lat2 = route_coords[i + 1]
        remaining_km += _haversine(lat1, lng1, lat2, lng2)

    return remaining_km, nearest_idx


def _confidence(
    observed_speed: float,
    predicted_speed: float,
    samples: int,
) -> float:
    """
    Confidence 0–1: starts low (few samples), degrades when
    observed speed diverges sharply from predicted.
    """
    sample_conf = min(1.0, samples / 5)
    speed_ratio = observed_speed / max(predicted_speed, 1.0) if observed_speed > 1 else 1.0
    deviation_penalty = max(0.0, 1.0 - abs(1.0 - speed_ratio))
    return round(sample_conf * 0.4 + deviation_penalty * 0.6, 3)


# ── ORS fetcher ─────

async def _fetch_ors_route(
    origin_lat: float, origin_lng: float,
    dest_lat: float, dest_lng: float,
) -> dict:
    """
    Call OpenRouteService directions API.
    Returns the raw JSON response.
    Falls back to straight-line geometry if ORS is unavailable.
    """
    # Try to get API key from settings if env var is empty
    api_key = ORS_API_KEY
    if not api_key:
        try:
            from app.core.config import settings
            api_key = settings.ors_api_key or ""
        except Exception:
            api_key = ""

    if not api_key:
        return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            resp = await client.post(
                ORS_BASE_URL,
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "coordinates": [
                        [origin_lng, origin_lat],
                        [dest_lng, dest_lat],
                    ],
                    "instructions": True,
                    "geometry": True,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        # Graceful degradation — synthesise a straight-line route
        return _fallback_route(origin_lat, origin_lng, dest_lat, dest_lng)


def _fallback_route(
    lat1: float, lon1: float, lat2: float, lon2: float,
) -> dict:
    """Straight-line fallback when ORS is unreachable."""
    dist = _haversine(lat1, lon1, lat2, lon2)
    # Interpolate 10 points along the straight line
    coords = [
        [lon1 + (lon2 - lon1) * i / 9, lat1 + (lat2 - lat1) * i / 9]
        for i in range(10)
    ]
    return {
        "_fallback": True,
        "routes": [{
            "summary": {"distance": dist * 1000, "duration": dist / 40 * 3600},
            "geometry": {"coordinates": coords},
            "segments": [{"steps": []}],
        }]
    }


# ── Main predictor class ─────

class ETAPredictor:
    """
    Stateful per-case ETA predictor.

    One instance should be shared across the app (e.g. as a FastAPI
    dependency or a module-level singleton). State is keyed by case_id.
    """

    def __init__(self):
        self._state: dict[int, _CaseState] = {}

    async def initial_eta(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        case_id: int,
        emergency: bool = True,
    ) -> RouteResult:
        """
        Fetch ORS route, compute initial ETA, cache state for live updates.
        Call once when a case is dispatched.
        """
        ors_data = await _fetch_ors_route(origin_lat, origin_lng, dest_lat, dest_lng)

        route = ors_data["routes"][0]
        route_distance_m: float = route["summary"]["distance"]
        route_distance_km = route_distance_m / 1000
        coords: list[list[float]] = route["geometry"]["coordinates"]
        step_count = len(route["segments"][0].get("steps", []))

        crow_km = _haversine(origin_lat, origin_lng, dest_lat, dest_lng)
        road_type = _road_type_hint(route_distance_km, crow_km, step_count)

        base_speed = _base_speed_kmh()
        road_factor = _road_speed_factor(road_type)
        traf_factor = 1.0   # no samples yet — neutral

        eta_min = _eta_minutes(route_distance_km, base_speed, road_factor, traf_factor, emergency)

        self._state[case_id] = _CaseState(
            initial_distance_km=route_distance_km,
            initial_eta_minutes=eta_min,
            last_eta_minutes=eta_min,
            last_lat=origin_lat,
            last_lng=origin_lng,
            last_ping_time=time.time(),
        )

        return RouteResult(
            case_id=case_id,
            route_coords=coords,
            total_distance_km=round(route_distance_km, 2),
            estimated_eta_minutes=eta_min,
            confidence=0.5,    # initial — few data points
            speed_used_kmh=round(base_speed * road_factor, 1),
            road_type_hint=road_type,
            traffic_factor=traf_factor,
            fetched_at=time.time(),
        )

    def update_eta(
        self,
        case_id: int,
        current_lat: float,
        current_lng: float,
        route_coords: list[list[float]],
        observed_speed_kmh: Optional[float] = None,
        emergency: bool = True,
    ) -> Optional[ETAUpdate]:
        """
        Called on every GPS ping (every ~3-5 seconds from ambulance).
        Returns a recalculated ETA based on current position and observed speed.
        """
        state = self._state.get(case_id)
        if not state:
            return None

        now = time.time()
        elapsed_s = now - state.last_ping_time

        # Derive observed speed from position delta if not provided by client
        if observed_speed_kmh is None and elapsed_s > 0:
            delta_km = _haversine(state.last_lat, state.last_lng, current_lat, current_lng)
            observed_speed_kmh = (delta_km / elapsed_s) * 3600   # km/h

        observed_speed_kmh = observed_speed_kmh or 0.0

        # Accumulate speed samples for traffic factor
        if observed_speed_kmh > 0:
            state.speed_samples.append(observed_speed_kmh)

        # Recalculate
        remaining_km, _ = _remaining_distance(current_lat, current_lng, route_coords)
        base_speed = _base_speed_kmh()
        road_type = _road_type_hint(remaining_km, remaining_km, 10)  # rough for live
        road_factor = _road_speed_factor(road_type)
        predicted_speed = base_speed * road_factor

        traf_factor = _traffic_factor(state.speed_samples, predicted_speed)
        new_eta = _eta_minutes(remaining_km, base_speed, road_factor, traf_factor, emergency)
        delta = new_eta - state.last_eta_minutes

        conf = _confidence(observed_speed_kmh, predicted_speed, len(state.speed_samples))
        congested = (
            len(state.speed_samples) >= 2
            and observed_speed_kmh < predicted_speed * _CONGESTION_THRESHOLD
            and observed_speed_kmh > 1.0
        )

        # Update state
        state.last_lat = current_lat
        state.last_lng = current_lng
        state.last_ping_time = now
        state.last_eta_minutes = new_eta

        return ETAUpdate(
            case_id=case_id,
            remaining_distance_km=round(remaining_km, 2),
            updated_eta_minutes=new_eta,
            delta_minutes=delta,
            confidence=conf,
            observed_speed_kmh=round(observed_speed_kmh, 1),
            predicted_speed_kmh=round(predicted_speed, 1),
            congested=congested,
            recalculated_at=now,
        )

    def clear_case(self, case_id: int) -> None:
        """Call when a case reaches 'arrived' or 'completed'."""
        self._state.pop(case_id, None)

    def active_cases(self) -> list[int]:
        return list(self._state.keys())


# Module-level singleton — import this everywhere
eta_predictor = ETAPredictor()
