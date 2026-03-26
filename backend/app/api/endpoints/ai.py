import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from anthropic import Anthropic
from app.core.config import settings

router = APIRouter(prefix="/api/ai", tags=["AI"])

# Initialize Claude client safely
client = Anthropic(api_key=settings.claude_api_key or "")

class CaseInput(BaseModel):
    input: str

@router.post("/analyze")
async def analyze_case(case: CaseInput):
    if not settings.claude_api_key:
        raise HTTPException(status_code=500, detail="CLAUDE_API_KEY is not configured in .env")
        
    try:
        # Rule Engine (Fast, Reliable Base)
        input_lower = case.input.lower()
        rule_severity = "UNKNOWN"
        
        if "unconscious" in input_lower and "head" in input_lower:
            rule_severity = "CRITICAL"
        elif "bleeding" in input_lower and "internal" in input_lower:
            rule_severity = "CRITICAL"
        elif "fracture" in input_lower and "bleeding" not in input_lower:
            rule_severity = "MODERATE"

        # Claude AI Enhancement
        prompt = f"""
        Analyze this emergency case using a hybrid rule-based approach. 
        The local rule engine already classified the base severity as: {rule_severity}.
        
        Return exactly this format (ONLY valid JSON, no markdown code blocks, no explanation):
        {{
          "condition": "...",
          "severity": "...",
          "equipment": ["..."],
          "reasoning": "..."
        }}
        
        Case: {case.input}
        """
        
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        text_resp = response.content[0].text.strip()
        if text_resp.startswith("```json"):
            text_resp = text_resp[7:]
        elif text_resp.startswith("```"):
            text_resp = text_resp[3:]
        if text_resp.endswith("```"):
            text_resp = text_resp[:-3]
            
        import json
        try:
            parsed = json.loads(text_resp.strip())
        except Exception as e:
            return {"error": "Invalid AI response", "raw": text_resp}
            
        # Normalization Layer
        mapping = {
            "oxygen": "ventilator",
            "life support": "icu",
            "brain scan": "ct_scan",
            "x-ray": "xray",
            "heart monitor": "ecg",
            "blood": "blood_bank",
            "defibrator": "defibrillator",
            "shock": "defibrillator",
            "surgery": "icu"
        }
        
        orig_equip = parsed.get("equipment", [])
        if isinstance(orig_equip, str):
            orig_equip = [x.strip() for x in orig_equip.split(',')]
            
        normalized = [mapping.get(e.lower(), e.lower()) for e in orig_equip]
        parsed["equipment"] = list(set(normalized))
        
        return {"result": parsed}
        
    except Exception as e:
        print(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
