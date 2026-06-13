"""
tests/test_cases.py — Case endpoint tests for Phase 3 timeline and status updates.
"""
import pytest
from unittest.mock import patch

from app.core.config import settings
from app.db.models import Case, Availability, CaseEvent, NotificationDelivery, User, WebhookDelivery
from sqlalchemy import func

class TestCaseTimelineEndpoint:
    def test_timeline_empty_before_any_updates(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        res = client.get(f"/api/cases/{case_id}/timeline", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["status"] == "dispatched"

    def test_timeline_returns_events_in_order(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=auth_headers)
        client.put(f"/api/cases/{case_id}/status", json={"status": "on_scene"}, headers=auth_headers)
        
        res = client.get(f"/api/cases/{case_id}/timeline", headers=auth_headers)
        data = res.json()
        assert len(data) == 3
        # Ensure ordered ascending by timestamp
        assert data[0]["status"] == "dispatched"
        assert data[1]["status"] == "en_route"
        assert data[2]["status"] == "on_scene"

    def test_timeline_any_hospital_can_view(self, client, auth_headers, hospital_headers, dispatch_case):
        """Universal Hospital Dashboard: any hospital account can view any case timeline."""
        case_id = dispatch_case
        res = client.get(f"/api/cases/{case_id}/timeline", headers=hospital_headers)
        assert res.status_code == 200

class TestCaseStatusUpdateEndpoint:
    def test_valid_linear_transition_succeeds(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["status"] == "en_route"

    def test_invalid_skip_transition_rejected(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "arrived"}, headers=auth_headers)
        assert res.status_code == 400
        assert "Invalid transition" in res.json()["detail"]

    def test_backwards_transition_rejected(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=auth_headers)
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "dispatched"}, headers=auth_headers)
        assert res.status_code == 400

    @pytest.mark.parametrize("status_seq", [
        [],
        ["en_route"],
        ["en_route", "on_scene"],
        ["en_route", "on_scene", "transporting"],
        ["en_route", "on_scene", "transporting", "arrived"]
    ])
    def test_cancel_from_any_state_succeeds(self, client, auth_headers, status_seq, dispatch_case):
        case_id = dispatch_case
        for s in status_seq:
            client.put(f"/api/cases/{case_id}/status", json={"status": s}, headers=auth_headers)
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "cancelled"}, headers=auth_headers)
        assert res.status_code == 200

    def test_transition_after_terminal_state_blocked(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        client.put(f"/api/cases/{case_id}/status", json={"status": "cancelled"}, headers=auth_headers)
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=auth_headers)
        assert res.status_code == 400

    def test_completed_restores_beds(self, client, auth_headers, db_session, dispatch_case_factory):
        before_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        case_id = dispatch_case_factory()
        
        # Advance to completed
        for s in ["en_route", "on_scene", "transporting", "arrived", "completed"]:
            client.put(f"/api/cases/{case_id}/status", json={"status": s}, headers=auth_headers)
            
        after_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        assert after_beds == before_beds

    def test_cancelled_always_restores_beds(self, client, auth_headers, db_session, dispatch_case_factory):
        before_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        case_id = dispatch_case_factory()
        
        client.put(f"/api/cases/{case_id}/status", json={"status": "cancelled"}, headers=auth_headers)
            
        after_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        assert after_beds == before_beds

    def test_cancel_mid_route_restores_beds(self, client, auth_headers, db_session, dispatch_case_factory):
        before_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        case_id = dispatch_case_factory()
        client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=auth_headers)
        client.put(f"/api/cases/{case_id}/status", json={"status": "on_scene"}, headers=auth_headers)
        client.put(f"/api/cases/{case_id}/status", json={"status": "cancelled"}, headers=auth_headers)
            
        after_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        assert after_beds == before_beds

    def test_double_complete_does_not_double_increment(self, client, auth_headers, db_session, dispatch_case):
        case_id = dispatch_case
        for s in ["en_route", "on_scene", "transporting", "arrived", "completed"]:
            client.put(f"/api/cases/{case_id}/status", json={"status": s}, headers=auth_headers)
            
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "completed"}, headers=auth_headers)
        assert res.status_code == 400

    def test_wrong_ambulance_cannot_update_status(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case
        # Register user B
        import os
        email = f"test_amb_{os.urandom(4).hex()}@test.com"
        client.post("/api/auth/register", json={"email": email, "password": "pass", "role": "ambulance"})
        token = client.post("/api/auth/login", json={"email": email, "password": "pass"}).json()["access_token"]
        auth_b = {"Authorization": f"Bearer {token}"}
        
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=auth_b)
        assert res.status_code == 403

    def test_any_hospital_can_update_status(self, client, auth_headers, hospital_headers, dispatch_case):
        """Universal Hospital Dashboard: any hospital account can update any case status."""
        case_id = dispatch_case
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=hospital_headers)
        assert res.status_code == 200

    def test_admin_can_update_any_case_status(self, client, auth_headers, admin_headers, dispatch_case):
        case_id = dispatch_case
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "en_route"}, headers=admin_headers)
        assert res.status_code == 200

    def test_status_update_persists_webhook_and_notification_rows(self, client, auth_headers, db_session, dispatch_case, monkeypatch):
        case_id = dispatch_case
        case = db_session.query(Case).filter(Case.id == case_id).first()
        assert case is not None

        # Ensure webhook enqueue path is enabled for persistence verification.
        monkeypatch.setattr(settings, "webhook_delivery_url", "https://example.test/webhook")
        monkeypatch.setattr(settings, "webhook_secret", "test-secret")

        # Ensure at least one hospital user with push token exists for arrived notifications.
        token_user = db_session.query(User).filter(
            User.hospital_id == case.assigned_hospital_id,
            User.fcm_token.is_not(None),
        ).first()
        if token_user is None:
            token_user = User(
                email="persist_notify@test.com",
                password_hash="hash",
                role="hospital",
                hospital_id=case.assigned_hospital_id,
                fcm_token="persist_token",
            )
            db_session.add(token_user)
            db_session.commit()

        def _capture_and_close(coro):
            coro.close()
            return None

        with patch("app.services.case_status_service.asyncio.create_task", side_effect=_capture_and_close), \
             patch("app.services.notification_service.send_push", return_value=True):
            for status in ["en_route", "on_scene", "transporting", "arrived"]:
                res = client.put(
                    f"/api/cases/{case_id}/status",
                    json={"status": status},
                    headers=auth_headers,
                )
                assert res.status_code == 200

        webhook_rows = db_session.query(WebhookDelivery).filter(WebhookDelivery.case_id == case_id).all()
        notification_rows = db_session.query(NotificationDelivery).filter(NotificationDelivery.case_id == case_id).all()

        assert len(webhook_rows) >= 1
        assert any(row.event_type == "case.status.updated" for row in webhook_rows)
        assert len(notification_rows) >= 1
        assert any(row.channel == "push" for row in notification_rows)
