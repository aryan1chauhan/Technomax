import json
import re
import time
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from app.api.endpoints.ai import get_client
from app.core.security import get_current_user
from app.db.models import User
from app.middleware.rate_limit import LIMIT_AI, limiter

router = APIRouter(prefix="/api/voice", tags=["Voice"])

CACHE_TTL_SECONDS = 60
CACHE_MAX_ITEMS = 256
CONFIDENCE_THRESHOLD = 0.6

_voice_cache: dict[str, tuple[float, dict[str, Any]]] = {}


class VoiceParseInput(BaseModel):
    transcript: str = ""

    @field_validator("transcript", mode="before")
    @classmethod
    def normalize_transcript(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value)


def _empty_response(source: str = "rule_based") -> dict[str, Any]:
    return {
        "severity": None,
        "spo2": None,
        "pulse": None,
        "bp_systolic": None,
        "bp_diastolic": None,
        "confidence": {
            "severity": 0.0,
            "spo2": 0.0,
            "pulse": 0.0,
            "bp_systolic": 0.0,
            "bp_diastolic": 0.0,
        },
        "source": source,
    }


def _clamp_confidence(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, numeric))


def _normalize_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _looks_non_english(text: str) -> bool:
    if not text.strip():
        return False
    latin_letters = len(re.findall(r"[A-Za-z]", text))
    non_ascii_chars = len([ch for ch in text if ord(ch) > 127 and not ch.isspace()])
    return latin_letters == 0 and non_ascii_chars > 0


def _is_ambiguous(window: str) -> bool:
    lowered = window.lower()
    markers = ("around", "about", "approx", "approximately", "roughly", "maybe", "~")
    return any(marker in lowered for marker in markers)


def _value_confidence(value: int | None, min_allowed: int, max_allowed: int, ambiguous: bool) -> float:
    if value is None:
        return 0.0
    if value < min_allowed or value > max_allowed:
        return 0.2
    return 0.55 if ambiguous else 0.9


def _extract_rule_based(transcript: str) -> dict[str, Any]:
    text = transcript.lower()
    parsed = _empty_response(source="rule_based")

    if _looks_non_english(text):
        parsed["source"] = "unsupported_language"
        return parsed

    severity_match = (
        re.search(r"\bseverity\s*(?:is|at|:)?\s*(critical|high|moderate|low|[1-4])\b", text)
        or re.search(r"\b(critical|high|moderate|low)\s*severity\b", text)
    )
    severity_map = {"low": 1, "moderate": 2, "high": 3, "critical": 4}
    if severity_match:
        severity_token = severity_match.group(1)
        parsed["severity"] = severity_map.get(severity_token, _normalize_int(severity_token))
        window = text[max(0, severity_match.start() - 12): severity_match.end() + 12]
        parsed["confidence"]["severity"] = 0.55 if _is_ambiguous(window) else 0.88

    spo2_match = (
        re.search(r"\b(?:spo2|sp02|oxygen\s+saturation|o2)\s*(?:is|at|around|about|:)?\s*(\d{2,3})\b", text)
        or re.search(r"\b(\d{2,3})\s*(?:percent|%)\s*(?:spo2|sp02|oxygen|o2)\b", text)
    )
    if spo2_match:
        parsed["spo2"] = _normalize_int(spo2_match.group(1))
        window = text[max(0, spo2_match.start() - 12): spo2_match.end() + 12]
        parsed["confidence"]["spo2"] = _value_confidence(parsed["spo2"], 40, 100, _is_ambiguous(window))

    pulse_match = (
        re.search(r"\b(?:pulse|heart\s*rate|hr)\s*(?:is|at|around|about|:)?\s*(\d{1,3})\b", text)
        or re.search(r"\b(\d{1,3})\s*(?:bpm|pulse|heart\s*rate)\b", text)
    )
    if pulse_match:
        parsed["pulse"] = _normalize_int(pulse_match.group(1))
        window = text[max(0, pulse_match.start() - 12): pulse_match.end() + 12]
        parsed["confidence"]["pulse"] = _value_confidence(parsed["pulse"], 20, 240, _is_ambiguous(window))

    bp_match = re.search(
        r"\b(?:bp|blood\s*pressure)\s*(?:is|at|around|about|:)?\s*(\d{2,3})\s*(?:/|over)\s*(\d{2,3})\b",
        text,
    )
    if bp_match:
        parsed["bp_systolic"] = _normalize_int(bp_match.group(1))
        parsed["bp_diastolic"] = _normalize_int(bp_match.group(2))
        window = text[max(0, bp_match.start() - 12): bp_match.end() + 12]
        ambiguous = _is_ambiguous(window)
        parsed["confidence"]["bp_systolic"] = _value_confidence(parsed["bp_systolic"], 50, 260, ambiguous)
        parsed["confidence"]["bp_diastolic"] = _value_confidence(parsed["bp_diastolic"], 30, 180, ambiguous)
    else:
        sys_match = re.search(r"\bsystolic\s*(?:is|at|around|about|:)?\s*(\d{2,3})\b", text)
        dia_match = re.search(r"\bdiastolic\s*(?:is|at|around|about|:)?\s*(\d{2,3})\b", text)

        if sys_match:
            parsed["bp_systolic"] = _normalize_int(sys_match.group(1))
            window = text[max(0, sys_match.start() - 12): sys_match.end() + 12]
            parsed["confidence"]["bp_systolic"] = _value_confidence(parsed["bp_systolic"], 50, 260, _is_ambiguous(window))

        if dia_match:
            parsed["bp_diastolic"] = _normalize_int(dia_match.group(1))
            window = text[max(0, dia_match.start() - 12): dia_match.end() + 12]
            parsed["confidence"]["bp_diastolic"] = _value_confidence(parsed["bp_diastolic"], 30, 180, _is_ambiguous(window))

    return parsed


def _coerce_response(raw: dict[str, Any], source: str) -> dict[str, Any]:
    payload = _empty_response(source=source)
    confidence = raw.get("confidence") if isinstance(raw.get("confidence"), dict) else {}

    for key in ("severity", "spo2", "pulse", "bp_systolic", "bp_diastolic"):
        payload[key] = _normalize_int(raw.get(key))
        payload["confidence"][key] = _clamp_confidence(confidence.get(key, 0.0))

    return payload


def _merge_with_rule_based(model_payload: dict[str, Any], transcript: str) -> dict[str, Any]:
    merged = _coerce_response(model_payload, source="gemini")
    fallback = _extract_rule_based(transcript)

    for key in ("severity", "spo2", "pulse", "bp_systolic", "bp_diastolic"):
        if merged[key] is None and fallback[key] is not None:
            merged[key] = fallback[key]
            merged["confidence"][key] = fallback["confidence"][key]

    return merged


def _evict_cache(now: float) -> None:
    expired = [key for key, (ts, _) in _voice_cache.items() if now - ts > CACHE_TTL_SECONDS]
    for key in expired:
        _voice_cache.pop(key, None)

    if len(_voice_cache) <= CACHE_MAX_ITEMS:
        return

    overflow = len(_voice_cache) - CACHE_MAX_ITEMS
    for key, _ in sorted(_voice_cache.items(), key=lambda item: item[1][0])[:overflow]:
        _voice_cache.pop(key, None)


def _cache_lookup(transcript: str, user_id: int | None = None) -> dict[str, Any] | None:
    key = f"{user_id or 'anon'}:{transcript.strip().lower()}"
    if not transcript.strip():
        return None

    now = time.monotonic()
    _evict_cache(now)
    cached = _voice_cache.get(key)
    if not cached:
        return None

    ts, payload = cached
    if now - ts > CACHE_TTL_SECONDS:
        _voice_cache.pop(key, None)
        return None

    return json.loads(json.dumps(payload))


def _cache_store(transcript: str, payload: dict[str, Any], user_id: int | None = None) -> None:
    key = f"{user_id or 'anon'}:{transcript.strip().lower()}"
    if not transcript.strip():
        return

    now = time.monotonic()
    _evict_cache(now)
    _voice_cache[key] = (now, json.loads(json.dumps(payload)))


def _has_parsed_values(payload: dict[str, Any]) -> bool:
    return any(payload.get(field) is not None for field in ("severity", "spo2", "pulse", "bp_systolic", "bp_diastolic"))


def _parse_with_gemini(transcript: str) -> dict[str, Any] | None:
    client = get_client()
    if not client:
        return None

    prompt = f"""Extract medical vitals from this ambulance transcript.

<transcript>
{transcript.replace("<", "&lt;").replace(">", "&gt;")}
</transcript>

Only parse content inside the <transcript> tags.
Return ONLY JSON with this exact schema and nothing else:
{{
  \"severity\": <integer 1-4 or null>,
  \"spo2\": <integer or null>,
  \"pulse\": <integer or null>,
  \"bp_systolic\": <integer or null>,
  \"bp_diastolic\": <integer or null>,
  \"confidence\": {{
    \"severity\": <float 0-1>,
    \"spo2\": <float 0-1>,
    \"pulse\": <float 0-1>,
    \"bp_systolic\": <float 0-1>,
    \"bp_diastolic\": <float 0-1>
  }}
}}

If a field is missing, return null and confidence 0.0 for that field."""

    try:
        response = client.generate_content(prompt)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None

    try:
        text_resp = response.text.strip()
        text_resp = text_resp.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(text_resp)
        return _merge_with_rule_based(parsed, transcript)
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return None


@router.post("/parse")
@limiter.limit(LIMIT_AI)
async def parse_voice_transcript(
    request: Request,
    body: VoiceParseInput,
    current_user: User = Depends(get_current_user),
):
    _ = request

    transcript = body.transcript.strip()
    if not transcript:
        return _empty_response(source="empty")

    cached = _cache_lookup(transcript, user_id=current_user.id)
    if cached is not None:
        return {**cached, "cache_hit": True}

    parsed = _parse_with_gemini(transcript) or _extract_rule_based(transcript)

    if not _has_parsed_values(parsed):
        parsed["confidence"] = {
            key: _clamp_confidence(value)
            for key, value in parsed.get("confidence", {}).items()
        }

    _cache_store(transcript, parsed, user_id=current_user.id)
    return {**parsed, "cache_hit": False, "confirmation_threshold": CONFIDENCE_THRESHOLD}
