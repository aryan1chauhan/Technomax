import os
import json
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError, field_validator
import google.generativeai as genai
from app.core.config import settings
from app.core.security import get_current_user
from app.db.models import User
from app.middleware.rate_limit import limiter, LIMIT_AI

router = APIRouter(prefix="/api/ai", tags=["AI"])

# FIX: Lazy-init client so a missing key doesn't crash startup
_client = None

MEDICAL_KEYWORDS = {
    "pain", "arrest", "bleed", "bleeding", "injury", "trauma", "stroke",
    "breath", "breathing", "unconscious", "seizure", "burn", "fracture",
    "chest", "head", "cardiac", "heart", "attack", "fall", "accident",
    "vomit", "fever", "swelling", "allergic", "diabetic", "pregnant",
    "labour", "delivery", "kidney", "renal", "spine", "spinal", "poison",
    "overdose", "asthma", "respiratory", "oxygen", "paralysis", "convulsion",
    "epilepsy", "sugar", "insulin", "blood", "baby", "birth", "drug",
    "toxic", "fire", "scald", "anaphyla", "allerg", "hepatic", "jaundice",
    "dialysis", "urine", "neck", "back", "congestive", "facial", "speech"
}

CRITICAL_EQUIPMENT = {"ventilator", "defibrillator"}
IMPORTANT_EQUIPMENT = {"icu", "trauma_care"}
OPTIONAL_EQUIPMENT = {"xray", "lab"}

EQUIPMENT_ALIASES = {
    "icu_equipment": "icu",
    "ct_scan": "xray",
    "x-ray": "xray",
    "x_ray": "xray",
    "blood_bank": "lab",
    "ecg_monitor": "lab",
}


def _normalize_equipment_name(value: str) -> str:
    token = str(value or "").strip().lower()
    return EQUIPMENT_ALIASES.get(token, token)


def _categorize_equipment(items: list[str]) -> dict[str, list[str]]:
    buckets = {
        "critical_equipment": [],
        "important_equipment": [],
        "optional_equipment": [],
    }
    for raw in items:
        normalized = _normalize_equipment_name(raw)
        if not normalized:
            continue
        if normalized in CRITICAL_EQUIPMENT:
            target = "critical_equipment"
        elif normalized in OPTIONAL_EQUIPMENT:
            target = "optional_equipment"
        else:
            target = "important_equipment"
        if normalized not in buckets[target]:
            buckets[target].append(normalized)
    return buckets

def _is_medical(text: str) -> bool:
    words = set(text.lower().split())
    # Also check substrings for compound words like "anaphylaxis"
    full = text.lower()
    return bool(words & MEDICAL_KEYWORDS) or any(k in full for k in MEDICAL_KEYWORDS)

def _non_medical_response() -> dict:
    return {
        "condition_label": None,
        "severity": 0,
        "severity_label": "Unknown",
        "recommended_equipment": [],
        "notes": "No medical condition detected. Please re-describe the emergency clearly.",
        "matched_condition_id": "none",
        "low_confidence": True
    }


def get_client():
    global _client
    if _client is None:
        api_key = (
            getattr(settings, "gemini_api_key", None)
            or os.getenv("GEMINI_API_KEY")
        )
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        _client = genai.GenerativeModel("gemini-1.5-flash")
    return _client


def _has_key() -> bool:
    return get_client() is not None


class CaseInput(BaseModel):
    input: str


@router.post("/analyze")
@limiter.limit(LIMIT_AI)
async def analyze_case(
    request: Request,
    case: CaseInput,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    if not _has_key():
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not configured in .env")

    # GUARD: Reject non-medical input
    if not _is_medical(case.input):
        return {"result": _non_medical_response()}

    try:
        input_lower = case.input.lower()
        rule_severity = "UNKNOWN"
        if "unconscious" in input_lower and "head" in input_lower:
            rule_severity = "CRITICAL"
        elif "bleeding" in input_lower and "internal" in input_lower:
            rule_severity = "CRITICAL"
        elif "fracture" in input_lower and "bleeding" not in input_lower:
            rule_severity = "MODERATE"

        # Escape user input to mitigate prompt injection
        escaped_input = case.input.replace("<", "&lt;").replace(">", "&gt;")

        prompt = f"""Analyze this emergency case. The local rule engine pre-classified severity as: {rule_severity}.

Return ONLY valid JSON, no markdown:
{{
  "condition": "...",
  "severity": "...",
  "equipment": ["..."],
  "reasoning": "..."
}}

<transcript>
{escaped_input}
</transcript>
Only parse content inside the <transcript> tags."""

        model = get_client()
        response = model.generate_content(prompt)
        text_resp = response.text.strip()
        text_resp = text_resp.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            parsed = json.loads(text_resp)
        except Exception:
            return {"error": "Invalid AI response", "raw": text_resp}

        mapping = {
            "oxygen": "ventilator", "life support": "icu",
            "brain scan": "ct_scan", "x-ray": "xray",
            "heart monitor": "ecg", "blood": "blood_bank",
            "defibrator": "defibrillator", "shock": "defibrillator",
            "surgery": "icu"
        }
        orig_equip = parsed.get("equipment", [])
        if isinstance(orig_equip, str):
            orig_equip = [x.strip() for x in orig_equip.split(',')]
        parsed["equipment"] = list(set(mapping.get(e.lower(), e.lower()) for e in orig_equip))

        return {"result": parsed}

    except Exception as e:
        print(f"AI analyze error: {e}")
        raise HTTPException(status_code=500, detail="AI analysis failed. Please try again.")


class VoiceInput(BaseModel):
    voice_text: str


# FIX: This is the endpoint Dispatch.jsx calls for voice analysis
# Route name matches what the frontend posts to: /api/ai/equipment-recommend
@router.post("/equipment-recommend")
@limiter.limit(LIMIT_AI)
async def recommend_equipment(
    request: Request,
    body: VoiceInput,
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    """
    Analyze voice transcript → return condition + recommended equipment.
    Called by Dispatch.jsx after the paramedic speaks.
    If API key missing, returns a graceful fallback instead of 500.
    """
    # GUARD: Reject non-medical input before hitting Claude or fallback
    if not _is_medical(body.voice_text):
        return _non_medical_response()
    client = get_client()

    # FIX: Graceful fallback when no API key — rule-based equipment suggestions
    # so the frontend shows something useful instead of "AI unavailable"
    if not client:
        return _rule_based_fallback(body.voice_text)

    try:
        # Escape user input to mitigate prompt injection
        escaped = body.voice_text.replace("<", "&lt;").replace(">", "&gt;")

        prompt = f"""You are a medical emergency dispatcher AI. A paramedic described an emergency.

Respond ONLY with valid JSON (no markdown, no preamble):
{{
  "condition_label": "Short condition name (max 4 words)",
  "severity": <integer 1-4, where 4=Critical>,
  "severity_label": "Low|Moderate|High|Critical",
    "critical_equipment": ["item1"],
    "important_equipment": ["item2"],
    "optional_equipment": ["item3"],
  "recommended_equipment": ["item1", "item2"],
  "notes": "One critical sentence for hospital",
  "matched_condition_id": "cardiac_arrest|chest_pain|stroke|trauma|respiratory|burns|poisoning|obstetric|pediatric|diabetic|other"
}}

<transcript>
{escaped}
</transcript>
Only parse content inside the <transcript> tags."""

        response = client.generate_content(prompt)

        text_resp = response.text.strip()
        text_resp = text_resp.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text_resp)
        recommended = parsed.get("recommended_equipment") or []
        if not isinstance(recommended, list):
            recommended = []

        provided_tiers = {
            "critical_equipment": parsed.get("critical_equipment"),
            "important_equipment": parsed.get("important_equipment"),
            "optional_equipment": parsed.get("optional_equipment"),
        }
        if any(not isinstance(v, list) for v in provided_tiers.values()):
            provided_tiers = _categorize_equipment(recommended)
        else:
            provided_tiers = {
                key: [_normalize_equipment_name(item) for item in values if item]
                for key, values in provided_tiers.items()
            }

        normalized_recommended = sorted(
            set(
                provided_tiers["critical_equipment"]
                + provided_tiers["important_equipment"]
                + provided_tiers["optional_equipment"]
            )
        )
        parsed.update(provided_tiers)
        parsed["recommended_equipment"] = normalized_recommended
        return parsed

    except json.JSONDecodeError as e:
        print(f"AI JSON parse error: {e}")
        return _rule_based_fallback(body.voice_text)
    except Exception as e:
        print(f"AI equipment-recommend error: {e}")
        # FIX: Return fallback instead of 500 so frontend still works
        return _rule_based_fallback(body.voice_text)


def _rule_based_fallback(text: str) -> dict:
    """
    FIX: When Claude API is unavailable, return a keyword-based suggestion
    so the frontend still shows equipment recommendations instead of an error.
    """
    t = text.lower()
    equipment = []
    condition_id = "other"
    condition_label = "General Emergency"
    severity = 2

    if any(w in t for w in ["cardiac", "heart", "arrest", "chest pain"]):
        equipment = ["defibrillator", "ecg_monitor", "ventilator"]
        condition_id = "cardiac_arrest"
        condition_label = "Cardiac Arrest"
        severity = 4
    elif any(w in t for w in ["stroke", "paralysis", "facial droop", "speech"]):
        equipment = ["ct_scan", "ventilator"]
        condition_id = "stroke"
        condition_label = "Stroke / TIA"
        severity = 4
    elif any(w in t for w in ["bleed", "blood", "trauma", "accident", "injury"]):
        equipment = ["blood_bank", "ventilator"]
        condition_id = "trauma"
        condition_label = "Trauma / Injury"
        severity = 3
    elif any(w in t for w in ["breath", "airway", "asthma", "respiratory", "oxygen"]):
        equipment = ["ventilator", "oxygen"]
        condition_id = "respiratory"
        condition_label = "Respiratory Failure"
        severity = 3
    elif any(w in t for w in ["burn", "fire", "scald"]):
        equipment = ["blood_bank"]
        condition_id = "burns"
        condition_label = "Burns"
        severity = 2
    elif any(w in t for w in ["poison", "overdose", "drug", "toxic"]):
        equipment = ["ventilator", "blood_bank"]
        condition_id = "poisoning"
        condition_label = "Poisoning / OD"
        severity = 2
    elif any(w in t for w in ["diabetic", "sugar", "glucose", "insulin"]):
        condition_id = "diabetic"
        condition_label = "Diabetic Emergency"
        severity = 2
    elif any(w in t for w in ["baby", "birth", "pregnant", "labour", "delivery"]):
        equipment = ["blood_bank"]
        condition_id = "obstetric"
        condition_label = "Obstetric Emergency"
        severity = 3
    elif any(w in t for w in ["kidney", "renal", "dialysis", "urine", "urinary"]):
        equipment = ["ventilator", "blood_bank", "icu_equipment"]
        condition_id = "kidney_failure"
        condition_label = "Kidney Failure"
        severity = 2
    elif any(w in t for w in ["liver", "jaundice", "hepatic"]):
        equipment = ["blood_bank", "ventilator", "icu_equipment"]
        condition_id = "liver_failure"
        condition_label = "Liver Failure"
        severity = 2
    elif any(w in t for w in ["seizure", "convulsion", "epilepsy", "fitting"]):
        equipment = ["ventilator", "ct_scan", "icu_equipment"]
        condition_id = "seizure"
        condition_label = "Seizure"
        severity = 2
    elif any(w in t for w in ["spine", "spinal", "neck injury", "back injury", "paralysed"]):
        equipment = ["ct_scan", "ventilator", "icu_equipment"]
        condition_id = "spinal_injury"
        condition_label = "Spinal Injury"
        severity = 3
    elif any(w in t for w in ["heart failure", "cardiac failure", "congestive"]):
        equipment = ["defibrillator", "ecg", "ventilator", "icu_equipment", "blood_bank"]
        condition_id = "heart_failure"
        condition_label = "Heart Failure"
        severity = 4
    elif any(w in t for w in ["allerg", "anaphyla", "bee sting", "swelling throat"]):
        equipment = ["ventilator"]
        condition_id = "allergic_reaction"
        condition_label = "Allergic Reaction"
        severity = 2

    return {
        "condition_label": condition_label,
        "severity": severity,
        "severity_label": ["", "Low", "Moderate", "High", "Critical"][severity],
        **_categorize_equipment(equipment),
        "recommended_equipment": sorted({_normalize_equipment_name(item) for item in equipment if item}),
        "notes": f"Rule-based assessment (AI offline). Voice: {text[:80]}",
        "matched_condition_id": condition_id,
    }


TRIAGE_SYSTEM_PROMPT = """You are a medical triage AI for an emergency dispatch system.
You MUST respond with valid JSON only — no markdown, no explanation, no preamble.

Required output schema:
{
  "condition": "<primary medical condition string>",
  "severity": "<exactly one of: critical | moderate | low>",
  "priority": <integer 1-10, where 10 is most urgent>,
    "critical_equipment": ["<item1>"],
    "important_equipment": ["<item2>"],
    "optional_equipment": ["<item3>"],
  "required_specialists": ["<specialist1>"],
  "reasoning": "<one sentence justification>"
}
"""


class TriageOutput(BaseModel):
    condition: str
    severity: str
    priority: int
    required_equipment: list[str] = []
    critical_equipment: list[str] = []
    important_equipment: list[str] = []
    optional_equipment: list[str] = []
    required_specialists: list[str] = []
    reasoning: str = ""

    @field_validator("required_equipment", "critical_equipment", "important_equipment", "optional_equipment", mode="before")
    @classmethod
    def normalize_equipment_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [_normalize_equipment_name(v)]
        if isinstance(v, list):
            return [_normalize_equipment_name(item) for item in v if item]
        return []

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        normalized = v.lower().strip()
        if normalized not in {"critical", "moderate", "low"}:
            raise ValueError("severity must be critical, moderate, or low")
        return normalized

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: int) -> int:
        if not (1 <= v <= 10):
            raise ValueError("priority must be 1-10")
        return v

    @field_validator("condition")
    @classmethod
    def validate_condition(cls, v: str) -> str:
        val = v.strip().lower()
        if not val:
            raise ValueError("condition cannot be empty")
        return val

    def fill_equipment_buckets(self):
        if not (self.critical_equipment or self.important_equipment or self.optional_equipment):
            buckets = _categorize_equipment(self.required_equipment)
            self.critical_equipment = buckets["critical_equipment"]
            self.important_equipment = buckets["important_equipment"]
            self.optional_equipment = buckets["optional_equipment"]

        merged = sorted(
            set(self.critical_equipment + self.important_equipment + self.optional_equipment)
        )
        self.required_equipment = merged
        return self


def parse_and_validate_ai_response(raw: str) -> tuple[TriageOutput | None, str | None]:
    if not isinstance(raw, str):
        return None, "AI response is not a string"

    try:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    except (TypeError, ValueError) as exc:
        return None, f"AI response normalization failed: {exc}"

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None, f"No JSON object found in AI response: {raw[:200]}"

    json_str = match.group(0)
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc} — raw: {json_str[:200]}"

    try:
        parsed = TriageOutput(**data)
        parsed.fill_equipment_buckets()
        return parsed, None
    except ValidationError as exc:
        return None, f"Triage validation error: {exc}"
