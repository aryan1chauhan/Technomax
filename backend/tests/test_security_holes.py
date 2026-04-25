import os

import pytest
from starlette.websockets import WebSocketDisconnect

from app.api.endpoints import tracking
from app.core.security import create_access_token, hash_password
from app.db.models import Case, User


class _NoCloseSession:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass


def _seed_user(db_session, *, email: str, role: str, hospital_id: int | None = None) -> User:
    user = User(
        email=email,
        password_hash=hash_password("pass123"),
        role=role,
        hospital_id=hospital_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _token_for(user: User) -> str:
    return create_access_token(
        data={"sub": user.email, "role": user.role, "hospital_id": user.hospital_id}
    )


def test_public_register_rejects_admin_role(client):
    """SEC-AUTH-ADMIN-001 @api @security @regression public self-registration cannot create admins."""
    email = f"public_admin_{os.urandom(4).hex()}@test.com"

    res = client.post("/api/auth/register", json={
        "email": email,
        "password": "pass123",
        "role": "admin",
    })

    assert res.status_code == 400
    assert "invalid role" in res.json()["detail"].lower()


def test_admin_create_user_route_requires_admin(client, auth_headers, admin_headers):
    """SEC-AUTH-ADMIN-002 @api @security admin creation is only available to existing admins."""
    blocked = client.post("/api/auth/admin/create-user", json={
        "email": f"blocked_admin_{os.urandom(4).hex()}@test.com",
        "password": "pass123",
        "role": "admin",
    }, headers=auth_headers)
    assert blocked.status_code == 403

    created = client.post("/api/auth/admin/create-user", json={
        "email": f"created_admin_{os.urandom(4).hex()}@test.com",
        "password": "pass123",
        "role": "admin",
    }, headers=admin_headers)
    assert created.status_code == 201


def test_hospitals_list_requires_authentication(client):
    """SEC-HOSPITALS-LIST-001 @api @security @regression anonymous hospital inventory access is blocked."""
    res = client.get("/api/hospitals/")

    assert res.status_code == 401


@pytest.mark.parametrize("path,payload", [
    ("/api/ai/analyze", {"input": "cardiac arrest with chest pain"}),
    ("/api/ai/equipment-recommend", {"voice_text": "cardiac arrest with chest pain"}),
])
def test_ai_endpoints_require_authentication(client, path, payload):
    """SEC-AI-AUTH-001 @api @security @regression anonymous AI calls are blocked before analysis."""
    res = client.post(path, json=payload)

    assert res.status_code == 401


def test_tracking_websocket_rejects_user_without_case_ownership(client, db_session, monkeypatch):
    """SEC-WS-OWNER-001 @integration @security @regression unrelated users cannot subscribe to a case."""
    owner = _seed_user(db_session, email=f"owner_{os.urandom(4).hex()}@test.com", role="ambulance")
    intruder = _seed_user(db_session, email=f"intruder_{os.urandom(4).hex()}@test.com", role="ambulance")
    case = Case(
        user_id=owner.id,
        condition="cardiac_arrest",
        equipment_needed=["ecg"],
        ambulance_lat=29.86,
        ambulance_lng=77.89,
        status="dispatched",
    )
    db_session.add(case)
    db_session.flush()
    monkeypatch.setattr(tracking, "SessionLocal", lambda: _NoCloseSession(db_session))

    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/track/{case.id}?token={_token_for(intruder)}"):
            pass

    assert exc.value.code == 4003


def test_tracking_websocket_rejects_invalid_status_transition(client, db_session, monkeypatch):
    """SEC-WS-TRANSITION-001 @integration @security @regression WebSocket status updates use transition rules."""
    owner = _seed_user(db_session, email=f"ws_owner_{os.urandom(4).hex()}@test.com", role="ambulance")
    case = Case(
        user_id=owner.id,
        condition="cardiac_arrest",
        equipment_needed=["ecg"],
        ambulance_lat=29.86,
        ambulance_lng=77.89,
        status="dispatched",
    )
    db_session.add(case)
    db_session.flush()
    monkeypatch.setattr(tracking, "SessionLocal", lambda: _NoCloseSession(db_session))

    with client.websocket_connect(f"/ws/track/{case.id}?token={_token_for(owner)}") as ws:
        ws.send_json({"type": "status", "status": "arrived"})
        message = ws.receive_json()

    db_session.refresh(case)
    assert message["type"] == "error"
    assert message["status_code"] == 400
    assert "Invalid transition" in message["message"]
    assert case.status == "dispatched"
