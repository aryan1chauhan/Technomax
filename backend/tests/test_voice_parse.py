import pytest

from app.api.endpoints import voice as voice_endpoint


@pytest.fixture(autouse=True)
def reset_voice_cache(monkeypatch):
    monkeypatch.setattr(voice_endpoint, "_voice_cache", {})


def test_voice_parse_clean_vitals_transcript(client, auth_headers, monkeypatch):
    """VOICE-PARSE-BE-CLEAN-001 @api @unit @validation parses complete vitals and confidence from clear transcript."""
    monkeypatch.setattr(voice_endpoint, "get_client", lambda: None)

    res = client.post(
        "/api/voice/parse",
        json={"transcript": "Severity critical, SpO2 is 91, heart rate 112, BP 88 over 60"},
        headers=auth_headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["severity"] == 4
    assert body["spo2"] == 91
    assert body["pulse"] == 112
    assert body["bp_systolic"] == 88
    assert body["bp_diastolic"] == 60
    assert body["confidence"]["spo2"] >= 0.6
    assert body["confidence"]["pulse"] >= 0.6


def test_voice_parse_partial_transcript_missing_fields(client, auth_headers, monkeypatch):
    """VOICE-PARSE-BE-PARTIAL-001 @api @unit @validation returns null for absent fields instead of omitting keys."""
    monkeypatch.setattr(voice_endpoint, "get_client", lambda: None)

    res = client.post(
        "/api/voice/parse",
        json={"transcript": "SpO2 94 only"},
        headers=auth_headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["spo2"] == 94
    assert body["pulse"] is None
    assert body["bp_systolic"] is None
    assert body["bp_diastolic"] is None
    assert body["severity"] is None


def test_voice_parse_ambiguous_transcript_marks_unconfirmed(client, auth_headers, monkeypatch):
    """VOICE-PARSE-BE-AMBIG-001 @api @unit @adversarial ambiguous values are extracted with low confidence."""
    monkeypatch.setattr(voice_endpoint, "get_client", lambda: None)

    res = client.post(
        "/api/voice/parse",
        json={"transcript": "Pulse around 130"},
        headers=auth_headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["pulse"] == 130
    assert body["confidence"]["pulse"] < 0.6


def test_voice_parse_empty_string_returns_nulls(client, auth_headers, monkeypatch):
    """VOICE-PARSE-BE-EMPTY-001 @api @unit @validation empty transcript is handled gracefully with null values."""
    monkeypatch.setattr(voice_endpoint, "get_client", lambda: None)

    res = client.post(
        "/api/voice/parse",
        json={"transcript": "   "},
        headers=auth_headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["severity"] is None
    assert body["spo2"] is None
    assert body["pulse"] is None
    assert body["bp_systolic"] is None
    assert body["bp_diastolic"] is None


def test_voice_parse_non_english_input_returns_nulls(client, auth_headers, monkeypatch):
    """VOICE-PARSE-BE-LANG-001 @api @unit @adversarial non-English input degrades gracefully with null outputs."""
    monkeypatch.setattr(voice_endpoint, "get_client", lambda: None)

    res = client.post(
        "/api/voice/parse",
        json={"transcript": "मरीज की सांस बहुत तेज चल रही है"},
        headers=auth_headers,
    )

    assert res.status_code == 200
    body = res.json()
    assert body["severity"] is None
    assert body["spo2"] is None
    assert body["pulse"] is None
    assert body["bp_systolic"] is None
    assert body["bp_diastolic"] is None
    assert body["source"] in {"rule_based", "unsupported_language"}


def test_voice_parse_caches_identical_transcript_for_60s(client, auth_headers, monkeypatch):
    """VOICE-PARSE-BE-CACHE-001 @api @integration @regression identical transcript responses are served from cache."""
    monkeypatch.setattr(voice_endpoint, "get_client", lambda: None)

    first = client.post(
        "/api/voice/parse",
        json={"transcript": "SpO2 93 pulse 118"},
        headers=auth_headers,
    )
    second = client.post(
        "/api/voice/parse",
        json={"transcript": "SpO2 93 pulse 118"},
        headers=auth_headers,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cache_hit"] is False
    assert second.json()["cache_hit"] is True
