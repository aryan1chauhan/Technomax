from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Union, Any
from datetime import datetime


class DispatchRequest(BaseModel):
    condition: str
    custom_condition: Optional[str] = None
    equipment_needed: list[str] = []
    # Alias for new scorer field name — accepts both frontend conventions
    required_equipment: list[str] = []
    ambulance_lat: float
    ambulance_lng: float
    severity: Optional[Union[str, int]] = None
    patient_age: Optional[int] = None
    patient_gender: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v):
        """Accept int (1=low, 2=moderate, 3=critical) or string severity."""
        if v is None:
            return None
        if isinstance(v, int):
            return {1: "low", 2: "moderate", 3: "critical"}.get(v, "moderate")
        return str(v).lower().strip()

    def get_equipment(self) -> list[str]:
        """Return whichever equipment list was populated."""
        return self.required_equipment or self.equipment_needed


# ── Enriched response schemas ────────────────────────────────────────────────

class ScoredHospitalResponse(BaseModel):
    hospital_id: int
    name: str
    distance_km: float
    available_beds: int
    icu_beds: int = 0
    score: float
    score_breakdown: dict[str, Any]
    explanation: list[str]
    pros: list[str]
    cons: list[str]
    data_source: str = "live"
    last_updated: Optional[str] = None
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None
    address: Optional[str] = None
    eta_minutes: Optional[int] = None


class RejectionSummary(BaseModel):
    missing_equipment: int
    insufficient_beds: int
    too_far: int
    total_rejected: int
    total_evaluated: int
    total_passed: int


class DispatchResponse(BaseModel):
    # ── New enriched fields ──
    case_id: Optional[int] = None
    status: Optional[str] = None
    triage: Optional[dict] = None
    selected_hospital: Optional[ScoredHospitalResponse] = None
    alternatives: list[ScoredHospitalResponse] = []
    rejected_hospitals: Optional[RejectionSummary] = None
    no_match: bool = False
    no_match_reason: Optional[str] = None
    fallback_options: list[str] = []
    triage_warning: Optional[str] = None
    error: Optional[str] = None

    # ── Legacy flat fields (derived from selected_hospital) ──
    hospital_id: Optional[int] = None
    hospital_name: Optional[str] = None
    address: Optional[str] = None
    final_score: Optional[float] = None
    confidence: Optional[float] = 0.0
    distance_km: Optional[float] = None
    eta_minutes: Optional[int] = None
    beds: Optional[int] = None
    icu: Optional[int] = None
    equipment_matched: list[str] = []
    equipment_missing: list[str] = []
    hospital_lat: Optional[float] = None
    hospital_lng: Optional[float] = None
    ml_reasoning: Optional[list[str]] = []


class CaseOut(BaseModel):
    id: int
    status: str
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
