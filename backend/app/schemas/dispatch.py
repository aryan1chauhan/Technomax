from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class DispatchRequest(BaseModel):
    condition: str
    custom_condition: Optional[str] = None
    equipment_needed: list[str] = []
    ambulance_lat: float
    ambulance_lng: float
    severity: Optional[int] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    notes: Optional[str] = None

class DispatchResponse(BaseModel):
    case_id: int
    hospital_id: int
    hospital_name: str
    address: str
    final_score: float
    confidence: float = 0.0
    distance_km: float
    eta_minutes: int
    beds: int
    icu: int
    equipment_matched: list[str]
    equipment_missing: list[str]
    hospital_lat: float
    hospital_lng: float
    ml_reasoning: list[str] = []

class CaseOut(BaseModel):
    id: int
    condition: str
    equipment_needed: list[str]
    ambulance_lat: float
    ambulance_lng: float
    assigned_hospital_id: Optional[int]
    final_score: Optional[float]
    distance_km: Optional[float]
    eta_minutes: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
