from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.middleware.rate_limit import limiter, LIMIT_CASES

router = APIRouter(prefix="/api/users", tags=["Users"])


class FCMTokenUpdate(BaseModel):
    token: str = Field(..., min_length=1)


@router.post("/fcm-token")
@limiter.limit(LIMIT_CASES)
def update_fcm_token(
    request: Request,  # noqa: ARG001
    token_data: FCMTokenUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = request
    current_user.fcm_token = token_data.token.strip()
    db.commit()
    return {"message": "FCM token updated"}
