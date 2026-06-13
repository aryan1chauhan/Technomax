import os
from unittest.mock import patch

from app.core.security import create_access_token, hash_password
from app.db.models import Case, CaseEvent, Hospital, NotificationDelivery, User


def _seed_user(db_session, *, role: str, hospital_id: int | None = None, fcm_token: str | None = None) -> User:
    user = User(
        email=f"{role}_{os.urandom(4).hex()}@test.com",
        password_hash=hash_password("pass123"),
        role=role,
        hospital_id=hospital_id,
        fcm_token=fcm_token,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _headers(user: User) -> dict:
    token = create_access_token(
        data={"sub": user.email, "role": user.role, "hospital_id": user.hospital_id}
    )
    return {"Authorization": f"Bearer {token}"}


def _case(db_session, case_id: int) -> Case:
    return db_session.query(Case).filter(Case.id == case_id).first()


def _seed_hospital(db_session) -> Hospital:
    hospital = Hospital(
        name=f"Workflow Hospital {os.urandom(2).hex()}",
        address="Test address",
        lat=29.86,
        lng=77.89,
    )
    db_session.add(hospital)
    db_session.commit()
    return hospital


def test_hospital_can_accept_dispatched_case_assigned_to_them(client, auth_headers, db_session, dispatch_case):
    """HOSP-ACCEPT-001 @api @security @integration @regression assigned hospital can accept."""
    case = _case(db_session, dispatch_case)
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=case.assigned_hospital_id)

    res = client.post(f"/api/cases/{case.id}/accept", headers=_headers(hospital_user))

    db_session.refresh(case)
    assert res.status_code == 200
    assert res.json()["status"] == "accepted"
    assert case.status == "accepted"


def test_hospital_can_accept_case_assigned_to_different_hospital(client, auth_headers, db_session, dispatch_case):
    """HOSP-ACCEPT-002 @api @security @regression hospital accept for different hospital is allowed (universal dashboard)."""
    case = _case(db_session, dispatch_case)
    original_hospital_id = case.assigned_hospital_id
    
    other_hospital = _seed_hospital(db_session)
    from app.db.models import Availability
    other_avail = Availability(hospital_id=other_hospital.id, beds=5, icu=2, accepting=True)
    db_session.add(other_avail)
    db_session.commit()
    
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=other_hospital.id)

    res = client.post(f"/api/cases/{case.id}/accept", headers=_headers(hospital_user))

    db_session.refresh(case)
    db_session.refresh(other_avail)
    
    assert res.status_code == 200
    assert case.status == "accepted"
    assert case.assigned_hospital_id == other_hospital.id
    # Check that bed count is decremented for the accepting hospital (5 -> 4)
    assert other_avail.beds == 4
    
    # Check that original hospital's bed was restored (+1)
    original_avail = db_session.query(Availability).filter(Availability.hospital_id == original_hospital_id).first()
    if original_avail:
        # Since the session setup sets it to GREATEST(beds, 5), and dispatch decremented it by 1, it was 4.
        # After restoring, it should go back to 5.
        assert original_avail.beds == 5


def test_hospital_can_decline_with_reason(client, auth_headers, db_session, dispatch_case):
    """HOSP-DECLINE-001 @api @security @integration @regression assigned hospital can decline with reason."""
    case = _case(db_session, dispatch_case)
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=case.assigned_hospital_id)

    res = client.post(
        f"/api/cases/{case.id}/decline",
        json={"reason": "No ICU team available"},
        headers=_headers(hospital_user),
    )

    db_session.refresh(case)
    event = db_session.query(CaseEvent).filter(
        CaseEvent.case_id == case.id,
        CaseEvent.status == "declined",
    ).first()
    assert res.status_code == 200
    assert case.status == "declined"
    assert event is not None
    assert event.note == "No ICU team available"


def test_declined_case_triggers_admin_notification(client, auth_headers, db_session, dispatch_case):
    """HOSP-DECLINE-NOTIFY-001 @integration @security @regression decline creates admin notification."""
    case = _case(db_session, dispatch_case)
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=case.assigned_hospital_id)
    admin_user = _seed_user(db_session, role="admin")

    res = client.post(
        f"/api/cases/{case.id}/decline",
        json={"reason": "CT unavailable"},
        headers=_headers(hospital_user),
    )

    delivery = db_session.query(NotificationDelivery).filter(
        NotificationDelivery.case_id == case.id,
        NotificationDelivery.user_id == admin_user.id,
        NotificationDelivery.channel == "in_app",
    ).first()
    assert res.status_code == 200
    assert delivery is not None
    assert delivery.payload["type"] == "case_declined"
    assert delivery.payload["reason"] == "CT unavailable"


def test_accepted_case_can_transition_to_en_route(client, auth_headers, db_session, dispatch_case):
    """HOSP-TRANSITION-001 @api @integration @regression accepted to en_route remains valid."""
    case = _case(db_session, dispatch_case)
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=case.assigned_hospital_id)
    client.post(f"/api/cases/{case.id}/accept", headers=_headers(hospital_user))

    res = client.put(f"/api/cases/{case.id}/status", json={"status": "en_route"}, headers=auth_headers)

    db_session.refresh(case)
    assert res.status_code == 200
    assert case.status == "en_route"


def test_invalid_hospital_workflow_transition_is_rejected(client, auth_headers, db_session, dispatch_case):
    """HOSP-TRANSITION-002 @api @security @regression invalid accepted to arrived shortcut is rejected."""
    case = _case(db_session, dispatch_case)
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=case.assigned_hospital_id)
    client.post(f"/api/cases/{case.id}/accept", headers=_headers(hospital_user))

    res = client.put(f"/api/cases/{case.id}/status", json={"status": "arrived"}, headers=auth_headers)

    db_session.refresh(case)
    assert res.status_code == 400
    assert case.status == "accepted"


def test_fcm_token_endpoint_updates_current_user(client, db_session):
    """HOSP-FCM-001 @api @security @regression authenticated user can register an FCM token."""
    hospital_user = _seed_user(db_session, role="hospital")

    res = client.post(
        "/api/users/fcm-token",
        json={"token": "fcm-token-123"},
        headers=_headers(hospital_user),
    )

    db_session.refresh(hospital_user)
    assert res.status_code == 200
    assert hospital_user.fcm_token == "fcm-token-123"


def test_dispatch_notification_service_creates_in_app_and_push_rows(db_session):
    """HOSP-DISPATCH-NOTIFY-001 @integration @regression dispatch notification creates in-app and push records."""
    from app.services.notification_service import send_dispatch_notifications
    import anyio

    hospital = _seed_hospital(db_session)
    hospital_user = _seed_user(db_session, role="hospital", hospital_id=hospital.id, fcm_token="fcm-token")
    ambulance_user = _seed_user(db_session, role="ambulance")
    case = Case(
        user_id=ambulance_user.id,
        condition="cardiac_arrest",
        equipment_needed=["ecg"],
        ambulance_lat=29.86,
        ambulance_lng=77.89,
        assigned_hospital_id=hospital.id,
        status="dispatched",
    )
    db_session.add(case)
    db_session.commit()

    async def _send():
        await send_dispatch_notifications(db=db_session, case=case, hospital_users=[hospital_user])

    with patch("app.services.notification_service.send_push", return_value=True):
        anyio.run(_send)

    rows = db_session.query(NotificationDelivery).filter(NotificationDelivery.case_id == case.id).all()
    assert {row.channel for row in rows} >= {"in_app", "push"}
    assert any(row.payload["type"] == "case_dispatched" for row in rows)


def test_universal_hospital_dashboard_permissions(client, db_session, dispatch_case):
    """HOSPITAL-UNIVERSAL-DASHBOARD-001 @api @security @integration
    Verify that any hospital user can fetch, view, and accept cases originally assigned to a different hospital (Universal Dashboard mode).
    """
    case = _case(db_session, dispatch_case)
    original_hospital_id = case.assigned_hospital_id

    # Create the other hospital availability
    other_hospital = _seed_hospital(db_session)
    from app.db.models import Availability
    other_avail = Availability(hospital_id=other_hospital.id, beds=10, icu=3, accepting=True)
    db_session.add(other_avail)
    db_session.commit()

    hospital_user = _seed_user(db_session, role="hospital", hospital_id=other_hospital.id)

    # 1. Verify get_hospital_cases returns the case even though it is assigned to another hospital
    get_res = client.get("/api/cases/hospital", headers=_headers(hospital_user))
    assert get_res.status_code == 200
    cases_list = get_res.json()
    assert any(c["id"] == case.id for c in cases_list)

    # 2. Verify we can accept the case
    accept_res = client.post(f"/api/cases/{case.id}/accept", headers=_headers(hospital_user))
    assert accept_res.status_code == 200

    db_session.refresh(case)
    db_session.refresh(other_avail)

    assert case.status == "accepted"
    assert case.assigned_hospital_id == other_hospital.id
    assert other_avail.beds == 9

    # Verify original hospital's bed was restored (+1)
    original_avail = db_session.query(Availability).filter(Availability.hospital_id == original_hospital_id).first()
    if original_avail:
        assert original_avail.beds == 5
