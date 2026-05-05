from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional, Union, Any
from datetime import datetime


class DispatchRequest(BaseModel):
    condition: str
    custom_condition: Optional[str] = None
    equipment_needed: list[str] = []
    # Alias for new scorer field name — accepts both frontend conventions
    required_equipment: list[str] = []
    critical_equipment: list[str] = []
    important_equipment: list[str] = []
    optional_equipment: list[str] = []
    ambulance_equipment: list[str] = []
    vitals: dict[str, Any] = {}
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
        """Return deduplicated equipment from flat and categorized inputs."""
        ordered: list[str] = []
        for item in (
            self.required_equipment
            + self.equipment_needed
            + self.critical_equipment
            + self.important_equipment
            + self.optional_equipment
        ):
            normalized = str(item or "").strip().lower()
            if normalized and normalized not in ordered:
                ordered.append(normalized)
        return ordered

    def get_severity_score(self) -> int:
        """Normalize severity into 1–10 scale for dispatch stage logic."""
        if self.severity is None:
            return 5

        if isinstance(self.severity, int):
            value = self.severity
        else:
            text = str(self.severity).strip().lower()
            if text.isdigit():
                value = int(text)
            else:
                value = {
                    "minor": 3,
                    "low": 3,
                    "moderate": 6,
                    "medium": 6,
                    "critical": 9,
                    "high": 9,
                }.get(text, 5)

        if value <= 3:
            return 3
        if value >= 8:
            return 9
        return 6


# ── Enriched response schemas ─────

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
    decision_type: Optional[str] = None
    primary_destination: Optional[dict[str, Any]] = None
    secondary_destination: Optional[dict[str, Any]] = None
    reasoning: Optional[dict[str, Any]] = None
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
    custom_condition: Optional[str] = None
    equipment_needed: list[str]
    ambulance_lat: float
    ambulance_lng: float
    assigned_hospital_id: Optional[int]
    final_score: Optional[float]
    distance_km: Optional[float]
    eta_minutes: Optional[int]
    severity_score: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
