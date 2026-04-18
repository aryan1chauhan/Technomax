from __future__ import annotations

import math
import time
from typing import Any

import httpx

OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
_OSRM_BACKOFF_SECONDS = 300
_OSRM_STATE = {"unavailable_until": 0.0}


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _haversine_km(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(dest_lat - origin_lat)
    d_lng = math.radians(dest_lng - origin_lng)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(origin_lat))
        * math.cos(math.radians(dest_lat))
        * math.sin(d_lng / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _fallback_eta_minutes(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> float:
    distance_km = _haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
    # Conservative default ambulance routing speed including urban traffic.
    eta = (distance_km / 40.0) * 60.0
    return max(0.1, round(eta, 2))


def get_eta(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float) -> float:
    """Return ETA in minutes using OSRM public API, falling back to haversine."""
    if time.time() < float(_OSRM_STATE["unavailable_until"]):
        return _fallback_eta_minutes(origin_lat, origin_lng, dest_lat, dest_lng)

    try:
        url = (
            f"{OSRM_ROUTE_URL}/"
            f"{_coerce_float(origin_lng):.6f},{_coerce_float(origin_lat):.6f};"
            f"{_coerce_float(dest_lng):.6f},{_coerce_float(dest_lat):.6f}"
        )
        params = {
            "overview": "false",
            "alternatives": "false",
            "steps": "false",
        }

        response = httpx.get(url, params=params, timeout=1.5)
        response.raise_for_status()
        payload = response.json()

        routes = payload.get("routes")
        if not isinstance(routes, list) or not routes:
            raise ValueError("OSRM response has no routes")

        duration_seconds = _coerce_float(routes[0].get("duration"), default=-1.0)
        if duration_seconds <= 0:
            raise ValueError("OSRM response missing valid duration")

        eta_minutes = duration_seconds / 60.0
        _OSRM_STATE["unavailable_until"] = 0.0
        return max(0.1, round(eta_minutes, 2))
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
        _OSRM_STATE["unavailable_until"] = time.time() + _OSRM_BACKOFF_SECONDS
        return _fallback_eta_minutes(origin_lat, origin_lng, dest_lat, dest_lng)


def set_haversine_only_mode(enabled: bool) -> None:
    """Enable/disable deterministic haversine-only ETA mode for simulations/tests."""
    _OSRM_STATE["unavailable_until"] = float("inf") if bool(enabled) else 0.0
