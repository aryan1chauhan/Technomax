"""
tests/test_dispatch.py — Dispatch endpoint tests.

Covers:
- Successful dispatch flow
- Non-ambulance role rejection
- Missing GPS coordinates
- Response schema validation
- Case creation verification
"""
import os
import pytest


class TestDispatchEndpoint:
    """Tests for POST /api/dispatch/"""

    def test_dispatch_success(self, client, auth_headers):
        """Valid dispatch request should return a hospital assignment."""
        res = client.post("/api/dispatch/", json={
            "condition": "cardiac_arrest",
            "equipment_needed": ["ecg", "defibrillator"],
            "ambulance_lat": 29.8601,
            "ambulance_lng": 77.8868,
        }, headers=auth_headers)
        
        # Either 200 (hospital found) or 404 (no hospitals in test DB)
        if res.status_code == 200:
            data = res.json()
            assert "case_id" in data
            assert "hospital_id" in data
            assert "hospital_name" in data
            assert "final_score" in data
            assert "distance_km" in data
            assert "eta_minutes" in data
            assert "ml_reasoning" in data
            assert isinstance(data["ml_reasoning"], list)
            assert data["final_score"] >= 0
            assert data["final_score"] <= 1
            assert data["eta_minutes"] >= 1
        else:
            assert res.status_code == 404
            assert "no suitable hospital" in res.json()["detail"].lower()

    def test_dispatch_non_ambulance_role(self, client, hospital_headers):
        """Hospital role should be rejected from dispatch."""
        res = client.post("/api/dispatch/", json={
            "condition": "trauma",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=hospital_headers)
        assert res.status_code == 403

    def test_dispatch_without_auth(self, client):
        """Dispatch without authentication should return 401."""
        res = client.post("/api/dispatch/", json={
            "condition": "stroke",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        })
        assert res.status_code == 401

    def test_dispatch_missing_condition(self, client, auth_headers):
        """Dispatch without condition field should return 422."""
        res = client.post("/api/dispatch/", json={
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=auth_headers)
        assert res.status_code == 422

    def test_dispatch_missing_gps(self, client, auth_headers):
        """Dispatch without GPS coordinates should return 422."""
        res = client.post("/api/dispatch/", json={
            "condition": "cardiac_arrest",
        }, headers=auth_headers)
        assert res.status_code == 422

    def test_dispatch_with_optional_fields(self, client, auth_headers):
        """Dispatch with all optional fields should work."""
        res = client.post("/api/dispatch/", json={
            "condition": "trauma",
            "custom_condition": "motorcycle accident",
            "equipment_needed": ["ventilator", "blood_bank"],
            "ambulance_lat": 30.0689,
            "ambulance_lng": 78.3001,
            "severity": 3,
            "patient_age": 35,
            "patient_gender": "male",
            "notes": "Patient conscious, multiple fractures",
        }, headers=auth_headers)
        # Should not fail on optional fields
        assert res.status_code in (200, 404)

    def test_dispatch_creates_case(self, client, auth_headers):
        """Successful dispatch should create a case visible in /api/cases/."""
        # Dispatch
        dispatch_res = client.post("/api/dispatch/", json={
            "condition": "fracture",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=auth_headers)
        
        if dispatch_res.status_code != 200:
            pytest.skip("No hospitals available in test DB")
        
        case_id = dispatch_res.json()["case_id"]
        
        # Verify case exists
        cases_res = client.get("/api/cases/", headers=auth_headers)
        assert cases_res.status_code == 200
        case_ids = [c["id"] for c in cases_res.json()]
        assert case_id in case_ids

    def test_dispatch_response_schema(self, client, auth_headers):
        """Dispatch response should contain all required fields."""
        res = client.post("/api/dispatch/", json={
            "condition": "stroke",
            "equipment_needed": ["ventilator"],
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=auth_headers)
        
        if res.status_code != 200:
            pytest.skip("No hospitals available in test DB")
        
        data = res.json()
        required_fields = [
            "case_id", "hospital_id", "hospital_name", "address",
            "final_score", "distance_km", "eta_minutes",
            "beds", "icu", "equipment_matched", "equipment_missing",
            "hospital_lat", "hospital_lng", "ml_reasoning",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_dispatch_decrements_beds(self, client, auth_headers, db_session):
        from app.db.models import Availability
        from sqlalchemy import func
        before_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        
        res = client.post("/api/dispatch/", json={
            "condition": "fracture",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=auth_headers)
        
        if res.status_code != 200:
            import pytest
            pytest.skip("No hospitals available in test DB")
            
        after_beds = db_session.query(func.sum(Availability.beds)).scalar() or 0
        assert after_beds == before_beds - 1

    def test_dispatch_creates_initial_event(self, client, auth_headers, db_session):
        from app.db.models import CaseEvent
        res = client.post("/api/dispatch/", json={
            "condition": "fracture",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=auth_headers)
        
        if res.status_code != 200:
            import pytest
            pytest.skip("No hospitals available in test DB")
            
        case_id = res.json()["case_id"]
        events = db_session.query(CaseEvent).filter(CaseEvent.case_id == case_id).all()
        assert len(events) == 1
        assert events[0].status == "dispatched"

    def test_dispatch_default_status_is_dispatched(self, client, auth_headers):
        res = client.post("/api/dispatch/", json={
            "condition": "fracture",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        }, headers=auth_headers)
        if res.status_code != 200:
            import pytest
            pytest.skip("No hospitals available in test DB")
        
        assert res.json()["status"] == "dispatched"


class TestCasesEndpoint:
    """Tests for GET /api/cases/"""

    def test_cases_empty_for_new_user(self, client, auth_headers):
        """New user should have no cases."""
        res = client.get("/api/cases/", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == []

    def test_hospital_cases_non_hospital(self, client, auth_headers):
        """Non-hospital user should be rejected from hospital cases."""
        res = client.get("/api/cases/hospital", headers=auth_headers)
        assert res.status_code == 403


class TestHealthEndpoint:
    """Tests for GET /health"""

    def test_health_check(self, client):
        """Health check should return OK with database status."""
        res = client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"

    def test_root_endpoint(self, client):
        """Root endpoint should return API status."""
        res = client.get("/")
        assert res.status_code == 200
        assert "running" in res.json()["status"].lower()


class TestORSFallback:
    """Tests for ORS ETA integration fallback behavior."""

    def test_ors_timeout_falls_back_to_haversine(self, client, auth_headers):
        """When ORS times out, dispatch should still succeed using haversine ETA."""
        from unittest.mock import patch, AsyncMock
        import httpx

        # Patch settings to have a real-looking ORS key (not dummy)
        with patch("app.api.endpoints.dispatch.settings") as mock_settings:
            mock_settings.ors_api_key = "real_ors_key_for_test"

            # Mock httpx.AsyncClient so the .get() raises a timeout
            mock_response = AsyncMock()
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(
                side_effect=httpx.TimeoutException("ORS timed out")
            )
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)

            with patch("app.api.endpoints.dispatch.httpx.AsyncClient", return_value=mock_client_instance):
                res = client.post("/api/dispatch/", json={
                    "condition": "cardiac_arrest",
                    "ambulance_lat": 29.86,
                    "ambulance_lng": 77.89,
                    "equipment_needed": ["ecg"]
                }, headers=auth_headers)

                if res.status_code == 404:
                    pytest.skip("No hospitals available in test DB")

                assert res.status_code == 200
                data = res.json()
                # Case dispatched successfully with haversine fallback
                assert data["eta_minutes"] >= 1
                assert data["distance_km"] > 0
                assert "case_id" in data

    def test_ors_non_200_falls_back_to_haversine(self, client, auth_headers):
        """When ORS returns a non-200 status, dispatch should still succeed."""
        from unittest.mock import patch, AsyncMock, MagicMock

        with patch("app.api.endpoints.dispatch.settings") as mock_settings:
            mock_settings.ors_api_key = "real_ors_key_for_test"

            # Mock httpx.AsyncClient so .get() returns a 503
            mock_resp = MagicMock()
            mock_resp.status_code = 503

            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_resp)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)

            with patch("app.api.endpoints.dispatch.httpx.AsyncClient", return_value=mock_client_instance):
                res = client.post("/api/dispatch/", json={
                    "condition": "cardiac_arrest",
                    "ambulance_lat": 29.86,
                    "ambulance_lng": 77.89,
                    "equipment_needed": ["ecg"]
                }, headers=auth_headers)

                if res.status_code == 404:
                    pytest.skip("No hospitals available in test DB")

                assert res.status_code == 200
                data = res.json()
                assert data["eta_minutes"] >= 1
                assert data["distance_km"] > 0

