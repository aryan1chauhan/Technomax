import httpx

from app.services import eta_service


def test_get_eta_uses_osrm_duration_when_available(monkeypatch):
    eta_service._OSRM_STATE["unavailable_until"] = 0.0

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": [{"duration": 900}]}

    monkeypatch.setattr(eta_service.httpx, "get", lambda *args, **kwargs: MockResponse())

    eta = eta_service.get_eta(30.3165, 78.0322, 29.8543, 77.8880)
    assert eta == 15.0


def test_get_eta_falls_back_to_haversine_on_http_error(monkeypatch):
    eta_service._OSRM_STATE["unavailable_until"] = 0.0

    def _raise(*args, **kwargs):
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(eta_service.httpx, "get", _raise)

    eta = eta_service.get_eta(30.3165, 78.0322, 29.8543, 77.8880)
    assert eta > 0.0


def test_get_eta_falls_back_on_malformed_osrm_payload(monkeypatch):
    eta_service._OSRM_STATE["unavailable_until"] = 0.0

    class BadResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": []}

    monkeypatch.setattr(eta_service.httpx, "get", lambda *args, **kwargs: BadResponse())

    eta = eta_service.get_eta(30.3165, 78.0322, 29.8543, 77.8880)
    assert eta > 0.0
