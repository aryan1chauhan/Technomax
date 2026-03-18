from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class HospitalBase(BaseModel):
    name: str
    address: str
    lat: float
    lng: float

class AvailabilityUpdate(BaseModel):
    beds: int
    icu: int
    doctors: int
    equipment: list[str]
    accepting: bool

class AvailabilityOut(BaseModel):
    id: int
    beds: int
    icu: int
    doctors: int
    equipment: list[str]
    accepting: bool
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)

class HospitalOut(BaseModel):
    id: int
    name: str
    address: str
    lat: float
    lng: float
    availability: Optional[AvailabilityOut] = None
    
    model_config = ConfigDict(from_attributes=True)
