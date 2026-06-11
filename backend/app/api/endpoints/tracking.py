"""
tracking.py — WebSocket endpoint with smart ETA broadcasting.

Upgraded from the original to add per-ping ETA recalculation via
the routing_service.ETAPredictor.

WebSocket message types (server → client):
  { type: "route_init",   coords, eta_minutes, total_distance_km, road_type, confidence }
  { type: "position",     lat, lng, eta_minutes, delta_minutes, remaining_km,
                          confidence, congested, observed_speed_kmh, predicted_speed_kmh }
  { type: "status_change", status }
  { type: "error",         message }
  { type: "ping" }         — keepalive

WebSocket message types (client → server):
  { type: "ping", lat, lng, speed_kmh? }     — ambulance sends GPS position
  { type: "status", status }                 — ambulance/hospital updates case status

Endpoints:
  /ws/track/{case_id}        — NEW: smart ETA tracking (bidirectional)
  /ws/ambulance/{case_id}    — LEGACY: kept for backward compat
  /ws/hospital/{case_id}     — LEGACY: kept for backward compat
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from app.core.config import settings
from app.db.database import SessionLocal
from app.db.models import Case, Hospital, User
from app.schemas.case import CaseStatusUpdate
from app.services.case_status_service import apply_case_status_update
from app.services.case_realtime import case_realtime_manager
from app.services.routing_service import eta_predictor

router = APIRouter()

# Per-case route geometry cache so we don't re-fetch ORS on every ping
_route_cache: dict[int, list[list[float]]] = {}


# ── JWT validation (reused from the original tracking.py) ─────────────────────

def _validate_ws_token(token: str | None) -> dict | None:
    """Validate JWT token from WebSocket query params. Returns decoded payload or None."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("sub") is None:
            return None
        return payload
    except JWTError:
        return None


def _user_can_access_case(user: User, case: Case) -> bool:
    if user.role == "admin":
        return True
    if user.role == "ambulance":
        return case.user_id == user.id
    if user.role == "hospital":
        return case.assigned_hospital_id == user.hospital_id
    return False


def _user_is_case_participant(user: User, case: Case) -> bool:
    if user.role == "ambulance":
        return case.user_id == user.id
    if user.role == "hospital":
        return case.assigned_hospital_id == user.hospital_id
    return False


def _get_ws_user(db, payload: dict) -> User | None:
    email = payload.get("sub")
    if not email:
        return None
    return db.query(User).filter(User.email == email).first()


async def _send(ws: WebSocket, payload: dict) -> None:
    """Safe send — swallows errors if connection is already closing."""
    try:
        await ws.send_json(payload)
    except Exception:
        pass


# ── NEW: Smart tracking endpoint ──────────────────────────────────────────────

@router.websocket("/ws/track/{case_id}")
async def track_case(
    websocket: WebSocket,
    case_id: int,
):
    # ── JWT auth via query param ──
    token = websocket.query_params.get("token")
    payload = _validate_ws_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Missing or invalid token")
        return

    db = SessionLocal()
    try:
        current_user = _get_ws_user(db, payload)
        if not current_user:
            await websocket.close(code=4001, reason="Missing or invalid token")
            return

        case = db.query(Case).filter(Case.id == case_id).first()
        if not case:
            await websocket.close(code=4004, reason="Case not found")
            return
        if not _user_can_access_case(current_user, case):
            await websocket.close(code=4003, reason="Not authorized for this case")
            return

        await websocket.accept()
        await case_realtime_manager.connect(case_id, websocket)

        # ── Initial route fetch + ETA ──
        if case_id not in _route_cache and case.assigned_hospital_id:
            hospital = db.query(Hospital).filter(
                Hospital.id == case.assigned_hospital_id
            ).first()
            if hospital:
                try:
                    route_result = await eta_predictor.initial_eta(
                        origin_lat=case.ambulance_lat,
                        origin_lng=case.ambulance_lng,
                        dest_lat=hospital.lat,
                        dest_lng=hospital.lng,
                        case_id=case_id,
                        emergency=True,
                    )
                    _route_cache[case_id] = route_result.route_coords
                    await _send(websocket, {
                        "type": "route_init",
                        "coords": route_result.route_coords,
                        "eta_minutes": route_result.estimated_eta_minutes,
                        "total_distance_km": route_result.total_distance_km,
                        "road_type": route_result.road_type_hint,
                        "confidence": route_result.confidence,
                    })
                except Exception as e:
                    await _send(websocket, {
                        "type": "error",
                        "message": f"Route fetch failed: {str(e)}",
                    })
    finally:
        db.close()

    # ── Main receive loop (without holding DB connection) ──
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive
                await _send(websocket, {"type": "ping"})
                continue
            except WebSocketDisconnect:
                break
            except RuntimeError as e:
                if "WebSocket is not connected" in str(e):
                    break
                raise

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            # ── GPS position ping from ambulance ──
            if msg_type == "ping":
                lat = msg.get("lat")
                lng = msg.get("lng")
                speed_kmh = msg.get("speed_kmh")

                if lat is None or lng is None:
                    continue

                route_coords = _route_cache.get(case_id, [])
                eta_update = eta_predictor.update_eta(
                    case_id=case_id,
                    current_lat=lat,
                    current_lng=lng,
                    route_coords=route_coords,
                    observed_speed_kmh=speed_kmh,
                    emergency=True,
                )

                broadcast_payload: dict = {
                    "type": "position",
                    "case_id": case_id,
                    "lat": lat,
                    "lng": lng,
                    "eta_minutes": eta_update.updated_eta_minutes if eta_update else None,
                    "delta_minutes": eta_update.delta_minutes if eta_update else 0,
                    "remaining_km": eta_update.remaining_distance_km if eta_update else None,
                    "confidence": eta_update.confidence if eta_update else 0.5,
                    "congested": eta_update.congested if eta_update else False,
                    "observed_speed_kmh": eta_update.observed_speed_kmh if eta_update else None,
                    "predicted_speed_kmh": eta_update.predicted_speed_kmh if eta_update else None,
                }
                await case_realtime_manager.broadcast(case_id, broadcast_payload)

                # Also forward to any hospital listener on the legacy endpoint
                if case_id in _legacy_manager.hospital_connections:
                    await _legacy_manager.forward_location(case_id, broadcast_payload)

            # ── Status change ──
            elif msg_type == "status":
                new_status = msg.get("status")
                if new_status:
                    db_update = SessionLocal()
                    try:
                        status_payload = await apply_case_status_update(
                            db=db_update,
                            case_id=case_id,
                            update_data=CaseStatusUpdate(status=new_status),
                            current_user=current_user,
                        )
                        # Clear predictor state when case is done
                        if new_status in ("arrived", "completed", "cancelled"):
                            eta_predictor.clear_case(case_id)
                            _route_cache.pop(case_id, None)

                        await case_realtime_manager.broadcast(case_id, {
                            "type": "status_change",
                            "case_id": case_id,
                            "status": status_payload["status"],
                        })
                    except HTTPException as exc:
                        await _send(websocket, {
                            "type": "error",
                            "message": exc.detail,
                            "status_code": exc.status_code,
                        })
                    finally:
                        db_update.close()

            elif msg_type in {"webrtc_offer", "webrtc_answer", "webrtc_ice_candidate", "call_end", "call_declined"}:
                # Note: 'case' and 'current_user' are already captured in scope
                # but 'case' might be stale. However for participant check it's mostly fine.
                # If we really want to be sure, we'd fetch case again.
                signal_payload = {
                    "type": msg_type,
                    "case_id": case_id,
                    "from_user_id": current_user.id,
                    "payload": msg.get("payload")
                }
                await case_realtime_manager.broadcast(case_id, signal_payload, exclude=websocket)

    finally:
        await case_realtime_manager.disconnect(case_id, websocket)


# ── LEGACY: Original ambulance/hospital endpoints (kept for backward compat) ─

class _ConnectionManager:
    def __init__(self):
        self.ambulance_connections: dict[int, WebSocket] = {}
        self.hospital_connections: dict[int, WebSocket] = {}

    async def connect_ambulance(self, case_id: int, websocket: WebSocket):
        await websocket.accept()
        self.ambulance_connections[case_id] = websocket

    async def connect_hospital(self, case_id: int, websocket: WebSocket):
        await websocket.accept()
        self.hospital_connections[case_id] = websocket

    async def forward_location(self, case_id: int, data: dict):
        if case_id in self.hospital_connections:
            try:
                await self.hospital_connections[case_id].send_json(data)
            except (ConnectionError, RuntimeError):
                del self.hospital_connections[case_id]

    def disconnect(self, case_id: int, role: str):
        if role == "ambulance":
            self.ambulance_connections.pop(case_id, None)
        else:
            self.hospital_connections.pop(case_id, None)


_legacy_manager = _ConnectionManager()


@router.websocket("/ws/ambulance/{case_id}")
async def websocket_ambulance(websocket: WebSocket, case_id: int):
    """Legacy ambulance WebSocket — forwards GPS data to hospital listener."""
    token = websocket.query_params.get("token")
    payload = _validate_ws_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Authentication required")
        return

    db = SessionLocal()
    try:
        current_user = _get_ws_user(db, payload)
        case = db.query(Case).filter(Case.id == case_id).first()
        if not current_user or not case:
            await websocket.close(code=1008, reason="Authentication required")
            return
        if not _user_can_access_case(current_user, case):
            await websocket.close(code=4003, reason="Not authorized for this case")
            return
    finally:
        db.close()

    await _legacy_manager.connect_ambulance(case_id, websocket)
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
            except asyncio.TimeoutError:
                await _send(websocket, {"type": "ping"})
                continue

            lat = data.get("lat")
            lng = data.get("lng")

            if lat is not None and lng is not None:
                route_coords = _route_cache.get(case_id, [])
                eta_update = eta_predictor.update_eta(
                    case_id=case_id,
                    current_lat=lat,
                    current_lng=lng,
                    route_coords=route_coords,
                    observed_speed_kmh=data.get("speed_kmh"),
                    emergency=True,
                )
                if eta_update:
                    data["eta_minutes"] = eta_update.updated_eta_minutes
                    data["remaining_km"] = eta_update.remaining_distance_km
                    data["confidence"] = eta_update.confidence
                    data["congested"] = eta_update.congested
                    data["observed_speed_kmh"] = eta_update.observed_speed_kmh
                    data["delta_minutes"] = eta_update.delta_minutes

            await _legacy_manager.forward_location(case_id, data)
    except WebSocketDisconnect:
        _legacy_manager.disconnect(case_id, "ambulance")
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            _legacy_manager.disconnect(case_id, "ambulance")
        else:
            raise


@router.websocket("/ws/hospital/{case_id}")
async def websocket_hospital(websocket: WebSocket, case_id: int):
    """Legacy hospital WebSocket — receives forwarded ambulance data."""
    token = websocket.query_params.get("token")
    payload = _validate_ws_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Authentication required")
        return

    db = SessionLocal()
    try:
        current_user = _get_ws_user(db, payload)
        case = db.query(Case).filter(Case.id == case_id).first()
        if not current_user or not case:
            await websocket.close(code=1008, reason="Authentication required")
            return
        if not _user_can_access_case(current_user, case):
            await websocket.close(code=4003, reason="Not authorized for this case")
            return
    finally:
        db.close()

    await _legacy_manager.connect_hospital(case_id, websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await _send(websocket, {"type": "ping"})
                continue
    except WebSocketDisconnect:
        _legacy_manager.disconnect(case_id, "hospital")
    except RuntimeError as e:
        if "WebSocket is not connected" in str(e):
            _legacy_manager.disconnect(case_id, "hospital")
        else:
            raise
