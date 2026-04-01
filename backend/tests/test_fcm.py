import pytest
from unittest.mock import patch, MagicMock
from app.core import firebase
from app.db.models import Case, User, Hospital

@pytest.fixture
def mock_settings():
    with patch("app.core.firebase.settings") as mock:
        yield mock

@pytest.fixture
def mock_firebase_apps():
    with patch("app.core.firebase.firebase_admin._apps", new={"mock": True}):
        yield

def test_init_firebase_dummy_path(mock_settings):
    mock_settings.firebase_service_account_path = "dummy_path"
    with patch("app.core.firebase.firebase_admin.initialize_app") as mock_init:
        firebase.init_firebase()
        mock_init.assert_not_called()

def test_init_firebase_success(mock_settings, mock_firebase_apps):
    mock_settings.firebase_service_account_path = "valid_path"
    with patch("app.core.firebase.firebase_admin._apps", new={}):
        with patch("app.core.firebase.credentials.Certificate") as mock_cert, \
             patch("app.core.firebase.firebase_admin.initialize_app") as mock_init:
            firebase.init_firebase()
            mock_cert.assert_called_once_with("valid_path")
            mock_init.assert_called_once()

def test_init_firebase_exception(mock_settings, mock_firebase_apps):
    mock_settings.firebase_service_account_path = "valid_path"
    with patch("app.core.firebase.firebase_admin._apps", new={}):
        with patch("app.core.firebase.credentials.Certificate", side_effect=Exception("Cert error")):
            # Should not raise, just log error
            firebase.init_firebase()

def test_send_push_no_token(mock_firebase_apps):
    assert firebase.send_push("", "title", "body") is False
    assert firebase.send_push(None, "title", "body") is False

def test_send_push_uninitialized():
    # apps object is empty dictionary
    with patch("app.core.firebase.firebase_admin._apps", new={}):
        assert firebase.send_push("token_xyz", "title", "body") is False

def test_send_push_success(mock_firebase_apps):
    with patch("app.core.firebase.messaging.send") as mock_send:
        mock_send.return_value = "projects/my-project/messages/12345"
        result = firebase.send_push("token_xyz", "Test Title", "Test Body")
        assert result is True
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert msg.token == "token_xyz"
        assert msg.notification.title == "Test Title"
        assert msg.notification.body == "Test Body"
        assert msg.data == {}

def test_send_push_with_data(mock_firebase_apps):
    with patch("app.core.firebase.messaging.send") as mock_send:
        result = firebase.send_push("token_xyz", "Title", "Body", data={"case_id": "99"})
        assert result is True
        msg = mock_send.call_args[0][0]
        assert msg.data == {"case_id": "99"}

def test_send_push_failure_swallowed(mock_firebase_apps):
    with patch("app.core.firebase.messaging.send", side_effect=Exception("FCM timeout")):
        with patch("app.core.firebase.logger.warning") as mock_warn:
            result = firebase.send_push("token_xyz", "Title", "Body")
            assert result is False
            mock_warn.assert_called_once()

def test_arrived_transition_triggers_fcm(client, auth_headers, db_session, dispatch_case):
    # Pre-configure hospital user with token
    hospital_user = db_session.query(User).filter(User.role == "hospital").first()
    if not hospital_user:
        # Create a hospital user if none exists
        hospital_user = User(email="hosp_fcm@test.com", password_hash="hash", role="hospital", hospital_id=1, fcm_token="hosp_token_123")
        db_session.add(hospital_user)
        db_session.commit()
    else:
        hospital_user.fcm_token = "hosp_token_123"
        db_session.commit()

    case_id = dispatch_case
    
    # Update hospital ID to force matchup if dispatch assigned a different hospital
    case = db_session.query(Case).filter(Case.id == case_id).first()
    hospital_user.hospital_id = case.assigned_hospital_id
    db_session.commit()

    with patch("app.api.endpoints.cases.send_push") as mock_send:
        for s in ["en_route", "on_scene", "transporting"]:
            client.put(f"/api/cases/{case_id}/status", json={"status": s}, headers=auth_headers)
            
        mock_send.assert_not_called()
        
        # Arrived transition should trigger FCM
        res = client.put(f"/api/cases/{case_id}/status", json={"status": "arrived"}, headers=auth_headers)
        assert res.status_code == 200
        
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs["token"] == "hosp_token_123"
        assert kwargs["title"] == "Ambulance Arrived"
        assert "case_id" in kwargs["data"]

def test_arrived_transition_multiple_hospital_tokens(client, auth_headers, db_session, dispatch_case):
    case_id = dispatch_case
    case = db_session.query(Case).filter(Case.id == case_id).first()
    
    # Add two users with tokens for the assigned hospital
    u1 = User(email="hosp1@test.com", password_hash="hash", role="hospital", hospital_id=case.assigned_hospital_id, fcm_token="token_A")
    u2 = User(email="hosp2@test.com", password_hash="hash", role="hospital", hospital_id=case.assigned_hospital_id, fcm_token="token_B")
    db_session.add_all([u1, u2])
    db_session.commit()
    
    with patch("app.api.endpoints.cases.send_push") as mock_send:
        for s in ["en_route", "on_scene", "transporting", "arrived"]:
            client.put(f"/api/cases/{case_id}/status", json={"status": s}, headers=auth_headers)
        
        assert mock_send.call_count >= 2
        tokens_called = [call.kwargs["token"] for call in mock_send.call_args_list]
        assert "token_A" in tokens_called
        assert "token_B" in tokens_called
