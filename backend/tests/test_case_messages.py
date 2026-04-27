import os

from app.api.endpoints import tracking
from app.core.security import create_access_token, hash_password
from app.db.models import Case, CaseMessage, Hospital, User


class _NoCloseSession:
    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass


def _make_user(db_session, *, email: str, role: str, hospital_id: int | None = None) -> User:
    user = User(
        email=email,
        password_hash=hash_password("pass123"),
        role=role,
        hospital_id=hospital_id,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_hospital(db_session, *, suffix: str) -> Hospital:
    hospital = Hospital(
        name=f"Realtime Test Hospital {suffix}",
        address="Sector 1",
        lat=30.31,
        lng=78.03,
    )
    db_session.add(hospital)
    db_session.flush()
    return hospital


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(data={
        "sub": user.email,
        "role": user.role,
        "hospital_id": user.hospital_id,
    })
    return {"Authorization": f"Bearer {token}"}


def _ws_token(user: User) -> str:
    return create_access_token(data={
        "sub": user.email,
        "role": user.role,
        "hospital_id": user.hospital_id,
    })


def test_case_messages_forbid_non_participants(client, db_session):
    """CASE-CHAT-AUTH-001 @api @security @integration @regression non-participants cannot read or post case chat."""
    hospital = _make_hospital(db_session, suffix=os.urandom(3).hex())
    owner = _make_user(db_session, email=f"msg_owner_{os.urandom(4).hex()}@test.com", role="ambulance")
    stranger = _make_user(db_session, email=f"msg_stranger_{os.urandom(4).hex()}@test.com", role="ambulance")
    case = Case(
        user_id=owner.id,
        condition="cardiac_arrest",
        equipment_needed=["ecg"],
        ambulance_lat=29.86,
        ambulance_lng=77.89,
        status="dispatched",
        assigned_hospital_id=hospital.id,
    )
    db_session.add(case)
    db_session.commit()

    read_res = client.get(f"/api/cases/{case.id}/messages", headers=_auth_headers(stranger))
    write_res = client.post(f"/api/cases/{case.id}/messages", json={"body": "Can you hear me?"}, headers=_auth_headers(stranger))

    assert read_res.status_code == 403
    assert write_res.status_code == 403


def test_case_message_post_broadcasts_chat_event(client, db_session, monkeypatch):
    """CASE-CHAT-WS-001 @integration @api @security @regression posting chat emits a live case WebSocket event."""
    hospital_record = _make_hospital(db_session, suffix=os.urandom(3).hex())
    ambulance = _make_user(db_session, email=f"msg_amb_{os.urandom(4).hex()}@test.com", role="ambulance")
    hospital = _make_user(
        db_session,
        email=f"msg_hosp_{os.urandom(4).hex()}@test.com",
        role="hospital",
        hospital_id=hospital_record.id,
    )
    case = Case(
        user_id=ambulance.id,
        condition="cardiac_arrest",
        equipment_needed=["ecg"],
        ambulance_lat=29.86,
        ambulance_lng=77.89,
        status="dispatched",
        assigned_hospital_id=hospital_record.id,
    )
    db_session.add(case)
    db_session.commit()
    monkeypatch.setattr(tracking, "SessionLocal", lambda: _NoCloseSession(db_session))

    with client.websocket_connect(f"/ws/track/{case.id}?token={_ws_token(ambulance)}") as amb_ws, \
         client.websocket_connect(f"/ws/track/{case.id}?token={_ws_token(hospital)}") as hosp_ws:
        post_res = client.post(
            f"/api/cases/{case.id}/messages",
            json={"body": "Vitals worsening, prepare triage bay."},
            headers=_auth_headers(ambulance),
        )
        amb_msg = amb_ws.receive_json()
        hosp_msg = hosp_ws.receive_json()

    db_rows = db_session.query(CaseMessage).filter(CaseMessage.case_id == case.id).all()

    assert post_res.status_code == 201
    assert len(db_rows) == 1
    assert amb_msg["type"] == "chat"
    assert hosp_msg["type"] == "chat"
    assert hosp_msg["message"]["body"] == "Vitals worsening, prepare triage bay."
    assert hosp_msg["message"]["sender_role"] == "ambulance"
