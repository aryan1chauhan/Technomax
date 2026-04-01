"""
tests/test_auth.py — Authentication endpoint tests.

Covers:
- Successful registration and login
- Duplicate email rejection
- Invalid credentials
- Invalid role rejection
- Token format validation
- Role-based access control
"""
import os
import pytest


class TestRegistration:
    """Tests for POST /api/auth/register"""

    def test_register_success(self, client):
        """New user with valid role should register successfully."""
        email = f"reg_{os.urandom(4).hex()}@test.com"
        res = client.post("/api/auth/register", json={
            "email": email,
            "password": "strongpass123",
            "role": "ambulance",
        })
        assert res.status_code == 201
        assert res.json()["message"] == "User registered successfully"

    def test_register_duplicate_email(self, client):
        """Registering the same email twice should fail with 400."""
        email = f"dup_{os.urandom(4).hex()}@test.com"
        
        # First registration
        res1 = client.post("/api/auth/register", json={
            "email": email,
            "password": "pass123",
            "role": "ambulance",
        })
        assert res1.status_code == 201
        
        # Duplicate registration
        res2 = client.post("/api/auth/register", json={
            "email": email,
            "password": "pass123",
            "role": "ambulance",
        })
        assert res2.status_code == 400
        assert "already registered" in res2.json()["detail"].lower()

    def test_register_invalid_role(self, client):
        """Registration with an invalid role should be rejected."""
        email = f"bad_{os.urandom(4).hex()}@test.com"
        res = client.post("/api/auth/register", json={
            "email": email,
            "password": "pass123",
            "role": "superadmin",  # invalid
        })
        assert res.status_code == 400
        assert "invalid role" in res.json()["detail"].lower()

    def test_register_hospital_without_id(self, client):
        """Hospital user can register without a hospital_id."""
        email = f"hosp_{os.urandom(4).hex()}@test.com"
        res = client.post("/api/auth/register", json={
            "email": email,
            "password": "pass123",
            "role": "hospital",
        })
        assert res.status_code == 201


class TestLogin:
    """Tests for POST /api/auth/login"""

    def test_login_success(self, client):
        """Valid credentials should return a JWT token."""
        email = f"login_{os.urandom(4).hex()}@test.com"
        client.post("/api/auth/register", json={
            "email": email,
            "password": "correct_password",
            "role": "ambulance",
        })
        
        res = client.post("/api/auth/login", json={
            "email": email,
            "password": "correct_password",
        })
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "ambulance"

    def test_login_wrong_password(self, client):
        """Wrong password should return 401."""
        email = f"wrong_{os.urandom(4).hex()}@test.com"
        client.post("/api/auth/register", json={
            "email": email,
            "password": "correct_password",
            "role": "ambulance",
        })
        
        res = client.post("/api/auth/login", json={
            "email": email,
            "password": "wrong_password",
        })
        assert res.status_code == 401
        assert "invalid" in res.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Login with non-existent email should return 401."""
        res = client.post("/api/auth/login", json={
            "email": "nobody@nowhere.com",
            "password": "anything",
        })
        assert res.status_code == 401

    def test_login_returns_hospital_id(self, client):
        """Hospital login should include hospital_id in response."""
        email = f"hlogin_{os.urandom(4).hex()}@test.com"
        client.post("/api/auth/register", json={
            "email": email,
            "password": "pass123",
            "role": "hospital",
        })
        
        res = client.post("/api/auth/login", json={
            "email": email,
            "password": "pass123",
        })
        assert res.status_code == 200
        assert "hospital_id" in res.json()


class TestProtectedEndpoints:
    """Tests for authentication-required endpoints."""

    def test_dispatch_without_token(self, client):
        """Accessing dispatch without token should return 401."""
        res = client.post("/api/dispatch/", json={
            "condition": "cardiac_arrest",
            "ambulance_lat": 29.86,
            "ambulance_lng": 77.89,
        })
        assert res.status_code == 401

    def test_cases_without_token(self, client):
        """Accessing cases without token should return 401."""
        res = client.get("/api/cases/")
        assert res.status_code == 401

    def test_admin_stats_non_admin(self, client, auth_headers):
        """Non-admin user should be rejected from admin stats."""
        res = client.get("/api/cases/admin/stats", headers=auth_headers)
        assert res.status_code == 403
        assert "admin" in res.json()["detail"].lower()

    def test_admin_stats_with_admin(self, client, admin_headers):
        """Admin user should access admin stats."""
        res = client.get("/api/cases/admin/stats", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert "total_hospitals" in data
        assert "total_beds" in data
