import pytest
from unittest.mock import AsyncMock, patch


class TestWebhookDeliveryIntegration:
    def test_status_update_enqueues_and_schedules_webhook(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case

        def _capture_and_close(coro):
            coro.close()
            return None

        with patch("app.services.case_status_service.enqueue_case_status_webhook", return_value=123) as mock_enqueue, \
             patch("app.services.case_status_service.process_webhook_delivery", new=AsyncMock()) as mock_process, \
             patch("app.services.case_status_service.asyncio.create_task", side_effect=_capture_and_close) as mock_create_task:
            res = client.put(
                f"/api/cases/{case_id}/status",
                json={"status": "en_route"},
                headers=auth_headers,
            )

        assert res.status_code == 200
        assert res.json()["status"] == "en_route"
        mock_enqueue.assert_called_once()
        mock_process.assert_called_once_with(123)
        mock_create_task.assert_called_once()

    def test_status_update_continues_when_webhook_enqueue_fails(self, client, auth_headers, dispatch_case):
        case_id = dispatch_case

        with patch("app.services.case_status_service.enqueue_case_status_webhook", side_effect=RuntimeError("table missing")):
            res = client.put(
                f"/api/cases/{case_id}/status",
                json={"status": "en_route"},
                headers=auth_headers,
            )

        assert res.status_code == 200
        assert res.json()["status"] == "en_route"
