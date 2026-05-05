import json
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

    # Cloud path: JSON string directly in env var
    sa_json = settings.firebase_service_account_json
    if sa_json:
        try:
            sa_dict = json.loads(sa_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is invalid") from exc

        cred = credentials.Certificate(sa_dict)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized from FIREBASE_SERVICE_ACCOUNT_JSON")
        return

    # Local path: file on disk
    sa_path = settings.firebase_service_account_path
    if not sa_path:
        raise RuntimeError(
            "Firebase credentials are required. "
            "Set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH."
        )

    try:
        cred = credentials.Certificate(sa_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load Firebase credentials from path: {sa_path}"
        ) from exc

    firebase_admin.initialize_app(cred)
    logger.info("Firebase initialized from file: %s", sa_path)

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
