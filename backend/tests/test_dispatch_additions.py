"""
test_dispatch_additions.py

Tests for the enriched DispatchResponse schema.
Uses existing fixtures from conftest.py (client, auth_headers).

Run with:
    cd backend
    python -m pytest tests/test_dispatch_additions.py -v
"""
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
        """score_breakdown must contain all sub-score keys including ml_confidence.

        Tags: @api @regression
        goal: Every score_breakdown dict returned by /api/dispatch/ contains
              the full set of factor keys the dispatch service populates.
        """
        resp = client.post("/api/dispatch/", json=self.BASE_PAYLOAD, headers=auth_headers)
        data = resp.json()
        if not data.get("no_match"):
            breakdown = data["selected_hospital"]["score_breakdown"]
            # ml_confidence was added when the ML scorer was introduced.
            # Forbidden outcome: missing any key means the frontend score display breaks.
            assert set(breakdown.keys()) == {
                "distance",
                "beds",
                "specialist",
                "equipment",
                "outcome",
                "ml_confidence",
            }

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

    def test_dispatch_uses_emergency_override_when_equipment_unavailable(self, client, auth_headers):
        """Non-critical mismatches should degrade to emergency override instead of hard no-match."""
        payload = {
            **self.BASE_PAYLOAD,
            "equipment_needed": ["hyperbaric_chamber_xyz_nonexistent"],
        }
        resp = client.post("/api/dispatch/", json=payload, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["no_match"] is False
        assert data["decision_type"] in {"direct", "stabilize_first", "emergency_override"}
        if data["decision_type"] == "emergency_override":
            reasoning = data.get("reasoning") or {}
            assert reasoning.get("emergency_override") is True
            assert "partial equipment match" in str(reasoning.get("override_message", "")).lower()

    def test_dispatch_no_match_has_fallback_options(self, client, auth_headers):
        """If a true no-match occurs, fallback options should still be strings."""
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

    def test_parses_categorized_equipment_schema(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        raw = (
            '{"condition": "cardiac arrest", "severity": "critical", "priority": 10, '
            '"critical_equipment": ["ventilator", "defibrillator"], '
            '"important_equipment": ["icu_equipment"], '
            '"optional_equipment": ["ct_scan"], '
            '"reasoning": "Life threatening"}'
        )
        result, err = parse_and_validate_ai_response(raw)
        assert err is None
        assert result is not None
        assert result.critical_equipment == ["ventilator", "defibrillator"]
        assert result.important_equipment == ["icu"]
        assert result.optional_equipment == ["xray"]
        assert "ventilator" in result.required_equipment

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

    def test_non_string_response_returns_error(self):
        from app.api.endpoints.ai import parse_and_validate_ai_response

        result, err = parse_and_validate_ai_response(None)
        assert result is None
        assert err is not None
        assert "not a string" in err.lower()


class TestDispatchInternals:
    def test_build_rejection_summary_populates_required_fields(self):
        from app.services.dispatch_service import _build_rejection_summary

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
