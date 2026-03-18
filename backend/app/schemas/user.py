from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = Field(..., description="Must be 'ambulance' or 'hospital'")
    hospital_id: Optional[int] = None

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    role: str
    hospital_id: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
