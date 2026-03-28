import os
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from app.core.config import settings

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
        # FIX: Try both common .env key names
        api_key = (
            getattr(settings, "claude_api_key", None)
            or getattr(settings, "anthropic_api_key", None)
            or os.getenv("ANTHROPIC_API_KEY")
            or os.getenv("CLAUDE_API_KEY")
        )
        if not api_key:
            return None
        _client = Anthropic(api_key=api_key)
    return _client


def _has_key() -> bool:
    return get_client() is not None


class CaseInput(BaseModel):
    input: str


@router.post("/analyze")
async def analyze_case(case: CaseInput):
    if not _has_key():
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not configured in .env")

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

        prompt = f"""Analyze this emergency case. The local rule engine pre-classified severity as: {rule_severity}.

Return ONLY valid JSON, no markdown:
{{
  "condition": "...",
  "severity": "...",
  "equipment": ["..."],
  "reasoning": "..."
}}

Case: {case.input}"""

        response = get_client().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )

        text_resp = response.content[0].text.strip()
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
        raise HTTPException(status_code=500, detail=str(e))


class VoiceInput(BaseModel):
    voice_text: str


# FIX: This is the endpoint Dispatch.jsx calls for voice analysis
# Route name matches what the frontend posts to: /api/ai/equipment-recommend
@router.post("/equipment-recommend")
async def recommend_equipment(body: VoiceInput):
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
        prompt = f"""You are a medical emergency dispatcher AI. A paramedic described an emergency:

"{body.voice_text}"

Respond ONLY with valid JSON (no markdown, no preamble):
{{
  "condition_label": "Short condition name (max 4 words)",
  "severity": <integer 1-4, where 4=Critical>,
  "severity_label": "Low|Moderate|High|Critical",
  "recommended_equipment": ["item1", "item2"],
  "notes": "One critical sentence for hospital",
  "matched_condition_id": "cardiac_arrest|chest_pain|stroke|trauma|respiratory|burns|poisoning|obstetric|pediatric|diabetic|other"
}}"""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}]
        )

        text_resp = response.content[0].text.strip()
        text_resp = text_resp.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text_resp)
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
        "recommended_equipment": equipment,
        "notes": f"Rule-based assessment (AI offline). Voice: {text[:80]}",
        "matched_condition_id": condition_id,
    }
