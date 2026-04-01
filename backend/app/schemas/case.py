from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

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
