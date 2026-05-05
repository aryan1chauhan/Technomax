from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any, Optional

class CaseEventOut(BaseModel):
    id: int
    case_id: int
    status: str
    actor_id: Optional[int]
    actor_role: Optional[str]
    note: Optional[str]
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class CaseStatusUpdate(BaseModel):
    status: str
    note: Optional[str] = None
    vitals: Optional[dict[str, Any]] = None
    severity_score: Optional[int] = None
    actual_eta_minutes: Optional[int] = None

class CaseDeclineRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class CaseMessageCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


class CaseMessageOut(BaseModel):
    id: int
    case_id: int
    sender_id: int
    sender_role: str
    sender_email: str
    body: str
    sent_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseMessagePage(BaseModel):
    items: list[CaseMessageOut]
    page: int
    limit: int
    total: int
