import json
import os
import logging
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings

logger = logging.getLogger(__name__)

def init_firebase():
    """Initialize Firebase Admin SDK.
    
    Prefers FIREBASE_SERVICE_ACCOUNT_JSON env var (JSON string, for Render/cloud).
    Falls back to FIREBASE_SERVICE_ACCOUNT_PATH (file path, for local Docker).
    """
    if firebase_admin._apps:
        return  # Already initialized

    try:
        # Cloud path: JSON string directly in env var
        sa_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
        if sa_json:
            sa_dict = json.loads(sa_json)
            cred = credentials.Certificate(sa_dict)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized from FIREBASE_SERVICE_ACCOUNT_JSON")
            return

        # Local path: file on disk
        sa_path = settings.firebase_service_account_path
        if not sa_path or sa_path == "dummy_path":
            logger.warning("Firebase not configured — push notifications disabled")
            return

        cred = credentials.Certificate(sa_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized from file: %s", sa_path)

    except Exception as e:
        logger.warning("Firebase init failed: %s", e)

def send_push(token: str, title: str, body: str, data: dict = None) -> bool:
    """
    Send a push notification to a specific FCM token.
    Returns True if successfully dispatched, False otherwise.
    Silent swallow on failures per requirements, but logs warnings.
    """
    if not token or not firebase_admin._apps:
        # If Firebase isn't initialized, we just return False and pretend not to fail hard
        return False

    if data is None:
        data = {}

    try:
        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data,
            token=token,
        )
        response = messaging.send(message)
        logger.info(f"Successfully sent message: {response}")
        return True
    except Exception as e:
        # Requirement: "silent swallow is fine for uptime, but add logger.warning("FCM send failed: %s", e) so failures surface in logs."
        logger.warning("FCM send failed: %s", e)
        return False
