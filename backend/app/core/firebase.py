import logging
import firebase_admin
from firebase_admin import credentials, messaging
from app.core.config import settings

logger = logging.getLogger(__name__)

def init_firebase():
    """Initialize Firebase Admin SDK with credentials from settings."""
    if not settings.firebase_service_account_path or settings.firebase_service_account_path == "dummy_path":
        logger.warning("Firebase not initialized: FIREBASE_SERVICE_ACCOUNT_PATH not set or is dummy.")
        return

    try:
        # Prevent re-initialization if already initialized
        if not firebase_admin._apps:
            # TODO: Drop in the real firebase-adminsdk credentials JSON file into the project.
            # Make sure the FIREBASE_SERVICE_ACCOUNT_PATH environment variable points to it.
            # e.g., FIREBASE_SERVICE_ACCOUNT_PATH=/app/credentials/firebase-service-account.json
            cred = credentials.Certificate(settings.firebase_service_account_path)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase Admin initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin: {e}")

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
