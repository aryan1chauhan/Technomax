from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import notification_service


@pytest.mark.asyncio
async def test_timeout_triggers_sms_fallback():
    db = MagicMock()
    case = SimpleNamespace(id=101)
    hospital_users = [SimpleNamespace(id=9, fcm_token="token-1")]

    push_delivery = SimpleNamespace(id=1, attempt_count=0, status="pending", last_error=None)
    sms_delivery = SimpleNamespace(id=2, attempt_count=0, status="pending", last_error=None)

    with patch("app.services.notification_service.settings.sms_fallback_number", "+10000000000"), \
         patch("app.services.notification_service._enqueue_delivery", side_effect=[push_delivery, sms_delivery]) as mock_enqueue, \
         patch("app.services.notification_service._mark_delivery") as mock_mark, \
         patch("app.services.notification_service._send_push_with_timeout", new=AsyncMock(return_value=(False, "push_timeout"))) as mock_push, \
         patch("app.services.notification_service._send_sms_with_timeout", new=AsyncMock(return_value=(True, None))) as mock_sms:
        await notification_service.send_arrival_notifications(db=db, case=case, hospital_users=hospital_users)

    mock_push.assert_awaited_once()
    mock_sms.assert_awaited_once()
    assert mock_enqueue.call_count == 2
    assert mock_mark.call_count == 2


@pytest.mark.asyncio
async def test_successful_push_skips_sms_fallback():
    db = MagicMock()
    case = SimpleNamespace(id=102)
    hospital_users = [SimpleNamespace(id=10, fcm_token="token-2")]

    push_delivery = SimpleNamespace(id=3, attempt_count=0, status="pending", last_error=None)

    with patch("app.services.notification_service.settings.sms_fallback_number", "+10000000000"), \
         patch("app.services.notification_service._enqueue_delivery", return_value=push_delivery) as mock_enqueue, \
         patch("app.services.notification_service._mark_delivery") as mock_mark, \
         patch("app.services.notification_service._send_push_with_timeout", new=AsyncMock(return_value=(True, None))) as mock_push, \
         patch("app.services.notification_service._send_sms_with_timeout", new=AsyncMock()) as mock_sms:
        await notification_service.send_arrival_notifications(db=db, case=case, hospital_users=hospital_users)

    mock_push.assert_awaited_once()
    mock_sms.assert_not_awaited()
    mock_enqueue.assert_called_once()
    mock_mark.assert_called_once()
