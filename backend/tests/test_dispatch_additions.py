"""
test_dispatch_additions.py

Tests for the enriched DispatchResponse schema.
Uses existing fixtures from conftest.py (client, auth_headers).

Run with:
    cd backend
    python -m pytest tests/test_dispatch_additions.py -v
"""
import pytest


class TestDispatchEnrichedResponse:
    """Tests for the new enriched DispatchResponse fields."""

    BASE_PAYLOAD = {
        "condition": "cardiac_arrest",
        "equipment_needed": ["defibrillator"],
        "ambulance_lat": 28.61,
        "ambulance_lng": 77.21,
    }

    def test_dispatch_returns_selected_hospital_object(self, client, auth_headers):
        """selected_hospital should be a nested object, not a flat field."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        if not data.get("no_match"):
            assert "selected_hospital" in data
            sh = data["selected_hospital"]
            assert "hospital_id" in sh
            assert "score" in sh
            assert "score_breakdown" in sh

    def test_dispatch_score_breakdown_has_all_factors(self, client, auth_headers):
        """score_breakdown must contain all four sub-score keys."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        if not data.get("no_match"):
            breakdown = data["selected_hospital"]["score_breakdown"]
            assert set(breakdown.keys()) == {"distance", "beds", "specialist", "equipment", "outcome"}

    def test_dispatch_returns_alternatives(self, client, auth_headers):
        """alternatives must be a list (empty or populated)."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        assert "alternatives" in data
        assert isinstance(data["alternatives"], list)

    def test_dispatch_alternatives_have_score_breakdown(self, client, auth_headers):
        """Each alternative must include score_breakdown."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        for alt in data.get("alternatives", []):
            assert "score_breakdown" in alt
            assert "explanation" in alt
            assert "pros" in alt
            assert "cons" in alt

    def test_dispatch_returns_rejected_hospitals_summary(self, client, auth_headers):
        """rejected_hospitals must always be present and contain count fields."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        assert "rejected_hospitals" in data
        if data["rejected_hospitals"] is not None:
            rh = data["rejected_hospitals"]
            assert "missing_equipment" in rh
            assert "total_rejected" in rh
            assert "total_evaluated" in rh

    def test_dispatch_no_match_when_equipment_unavailable(self, client, auth_headers):
        """Requesting nonexistent equipment should trigger no_match."""
        payload = {
            **self.BASE_PAYLOAD,
            "equipment_needed": ["hyperbaric_chamber_xyz_nonexistent"],
        }
        resp = client.post("/api/dispatch/", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["no_match"] is True
        assert data["no_match_reason"] is not None
        assert isinstance(data["fallback_options"], list)

    def test_dispatch_no_match_has_fallback_options(self, client, auth_headers):
        """no_match response should include partial-match fallback suggestions."""
        payload = {
            **self.BASE_PAYLOAD,
            "equipment_needed": ["hyperbaric_chamber_xyz_nonexistent"],
        }
        resp = client.post("/api/dispatch/", json=payload, headers=auth_headers)
        data = resp.json()
        if data.get("no_match"):
            assert "fallback_options" in data
            for opt in data["fallback_options"]:
                assert isinstance(opt, str)

    def test_dispatch_legacy_flat_fields_present(self, client, auth_headers):
        """Legacy flat fields must match selected_hospital so Map.jsx works."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        if not data.get("no_match"):
            assert "hospital_id" in data
            assert "hospital_name" in data
            assert "distance_km" in data
            assert "eta_minutes" in data
            assert "hospital_lat" in data
            assert "hospital_lng" in data
            assert data["hospital_id"] == data["selected_hospital"]["hospital_id"]
            assert data["distance_km"] == data["selected_hospital"]["distance_km"]

    def test_dispatch_critical_severity_accepted(self, client, auth_headers):
        """Explicitly passing severity override should not crash."""
        payload = {**self.BASE_PAYLOAD, "severity": "critical"}
        resp = client.post("/api/dispatch/", json=payload, headers=auth_headers)
        assert resp.status_code == 200

    def test_dispatch_triage_block_in_response(self, client, auth_headers):
        """triage dict should reflect the submitted condition and severity."""
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        if data.get("triage"):
            assert "condition" in data["triage"]
            assert "severity" in data["triage"]


class TestDispatchAiTriageValidation:
    """Unit tests for parse_and_validate_ai_response and TriageOutput."""

    def test_valid_json_parses_correctly(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        raw = '{"condition": "cardiac arrest", "severity": "critical", "priority": 10, "required_equipment": ["defibrillator"], "reasoning": "Life threatening"}'
        result, err = parse_and_validate_ai_response(raw)
        assert err is None
        assert result is not None
        assert result.severity == "critical"
        assert result.priority == 10

    def test_strips_markdown_fences(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        raw = '```json\n{"condition": "stroke", "severity": "critical", "priority": 9, "required_equipment": [], "reasoning": "Brain bleed"}\n```'
        result, err = parse_and_validate_ai_response(raw)
        assert err is None
        assert result.condition == "stroke"

    def test_invalid_severity_returns_error(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        raw = '{"condition": "burns", "severity": "urgent", "priority": 7, "required_equipment": [], "reasoning": "test"}'
        result, err = parse_and_validate_ai_response(raw)
        assert result is None
        assert err is not None
        assert "severity" in err.lower()

    def test_priority_out_of_range_returns_error(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        raw = '{"condition": "burns", "severity": "moderate", "priority": 15, "required_equipment": [], "reasoning": "test"}'
        result, err = parse_and_validate_ai_response(raw)
        assert result is None
        assert "priority" in err.lower()

    def test_no_json_in_response_returns_error(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        result, err = parse_and_validate_ai_response("Sorry, I cannot help with that.")
        assert result is None
        assert err is not None


class TestDispatchInternals:
    def test_build_rejection_summary_populates_required_fields(self):
        from app.api.endpoints.dispatch import _build_rejection_summary

        hospitals = [
            {"equipment": ["ecg"], "available_beds": 1},
            {"equipment": [], "available_beds": 0},
        ]
        ranked = [{"id": 1}]

        summary = _build_rejection_summary(
            hospital_dicts=hospitals,
            ranked=ranked,
            required_equipment=["ecg", "defibrillator"],
        )

        assert summary.total_evaluated == 2
        assert summary.total_passed == 1
        assert summary.total_rejected == 1
        assert summary.missing_equipment == 2
        assert summary.insufficient_beds == 1
        assert summary.too_far == 0
