# Code Review Bundle

Here are the three requested files consolidated for your review.

## 1. backend/api/routes/dispatch.py

```python
"""Minimal FAST dispatch endpoint.

Guardrails:
- NEVER run replay in dispatch.
- NEVER run learning in API.
- NEVER run simulation in API.
"""

from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
import uuid
import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, Field

from core.dispatch_engine import run_dispatch


router = APIRouter()
logger = logging.getLogger(__name__)


class DispatchPayload(BaseModel):
    case_id: str | None = None
    hospitals: list[dict[str, Any]] = Field(default_factory=list)
    ambulance_lat: float
    ambulance_lng: float
    condition_type: str
    severity_score: int | str | None = None
    vitals: dict[str, Any] | None = None
    ambulance_equipment: list[str] | None = None
    required_equipment: list[str] = Field(default_factory=list)
    forced_hospital_types: list[str] | None = None
    force_direct: bool = False
    relax_important_constraints: bool = False
    enable_adaptive_constraints: bool = True
    scenario_context: dict[str, Any] | None = None


def _enqueue_audit_log_non_blocking(result: dict[str, Any]) -> None:
    """Best-effort async trigger; failures must not impact FAST-path response."""
    try:
        from async_queue.tasks import enqueue_audit_log

        enqueue_audit_log(result)
    except (ImportError, OSError, RuntimeError, ValueError, TypeError, KeyError):
        # Intentionally swallow errors to keep dispatch latency isolated.
        return


def _build_audit_event(payload: DispatchPayload, result: dict[str, Any]) -> dict[str, Any]:
    case_id = payload.case_id or result.get("case_id") or result.get("decision_id")
    return {
        "case_id": case_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "input": payload.model_dump(),
        "output": result,
    }


@router.post("/dispatch")
async def dispatch_case(payload: DispatchPayload, background_tasks: BackgroundTasks) -> dict[str, Any]:
    case_id = payload.case_id or str(uuid.uuid4())
    forced_types = set(payload.forced_hospital_types) if payload.forced_hospital_types else None
    result = await run_dispatch(
        case_id=case_id,
        hospitals=payload.hospitals,
        ambulance_lat=payload.ambulance_lat,
        ambulance_lng=payload.ambulance_lng,
        condition_type=payload.condition_type,
        severity_score=payload.severity_score,
        vitals=payload.vitals,
        ambulance_equipment=payload.ambulance_equipment,
        required_equipment=payload.required_equipment,
        forced_hospital_types=forced_types,
        force_direct=payload.force_direct,
        relax_important_constraints=payload.relax_important_constraints,
        enable_adaptive_constraints=payload.enable_adaptive_constraints,
        scenario_context=payload.scenario_context,
    )
    result["case_id"] = case_id

    audit_event = _build_audit_event(payload, result)
    logger.info("ENQUEUE CALLED %s", result.get("case_id"))
    background_tasks.add_task(_enqueue_audit_log_non_blocking, audit_event)
    return result
```

<hr>

## 2. frontend/src/pages/Dispatch.jsx

```jsx
// frontend/src/pages/Dispatch.jsx
import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

const CONDITION_EQUIPMENT = {
  cardiac_arrest:    ["defibrillator", "ventilator", "ecg", "blood_bank", "icu_equipment"],
  chest_pain:        ["ecg", "ventilator", "blood_bank"],
  stroke:            ["ct_scan", "ventilator", "blood_bank", "icu_equipment"],
  trauma:            ["blood_bank", "ventilator", "icu_equipment", "ct_scan"],
  respiratory:       ["ventilator", "icu_equipment"],
  burns:             ["ventilator", "blood_bank", "icu_equipment"],
  poisoning:         ["ventilator", "icu_equipment"],
  obstetric:         ["blood_bank", "ventilator", "icu_equipment"],
  pediatric:         ["ventilator", "icu_equipment"],
  diabetic:          ["blood_bank", "icu_equipment"],
  fracture:          ["ct_scan"],
  snake_bite:        ["blood_bank", "ventilator"],
  drowning:          ["ventilator", "icu_equipment", "defibrillator"],
  electrocution:     ["defibrillator", "ventilator", "ecg"],
  seizure:           ["ventilator", "ct_scan", "icu_equipment"],
  allergic_reaction: ["ventilator"],
  heart_failure:     ["defibrillator", "ecg", "ventilator", "icu_equipment", "blood_bank"],
  kidney_failure:    ["ventilator", "blood_bank", "icu_equipment"],
  liver_failure:     ["blood_bank", "ventilator", "icu_equipment"],
  spinal_injury:     ["ct_scan", "ventilator", "icu_equipment"],
};

const EQUIPMENT_LABELS = {
  defibrillator: "Defibrillator",
  ventilator:    "Ventilator",
  ecg:           "ECG Monitor",
  ct_scan:       "CT Scan",
  blood_bank:    "Blood Bank",
  icu_equipment: "ICU Equipment",
};

const ALL_EQUIPMENT = Object.keys(EQUIPMENT_LABELS);

const CONDITIONS = [
  { id: "cardiac_arrest",    label: "Cardiac Arrest",    icon: "♥",  color: "#EE3B3B" },
  { id: "chest_pain",        label: "Chest Pain",        icon: "⚡", color: "#FF6B35" },
  { id: "stroke",            label: "Stroke / TIA",      icon: "🧠", color: "#9B59B6" },
  { id: "trauma",            label: "Trauma / Injury",   icon: "🩹", color: "#E67E22" },
  { id: "respiratory",       label: "Respiratory",        icon: "💨", color: "#3498DB" },
  { id: "burns",             label: "Burns",              icon: "🔥", color: "#E74C3C" },
  { id: "poisoning",         label: "Poisoning / OD",    icon: "☠",  color: "#2ECC71" },
  { id: "obstetric",         label: "Obstetric",          icon: "🤰", color: "#E91E8C" },
  { id: "pediatric",         label: "Pediatric",          icon: "👶", color: "#00BCD4" },
  { id: "diabetic",          label: "Diabetic Emergency", icon: "💉", color: "#FF9800" },
  // FIX: Added kidney_failure as selectable condition — was in CONDITION_EQUIPMENT but not CONDITIONS
  { id: "kidney_failure",    label: "Kidney Failure",     icon: "🫘", color: "#6C5CE7" },
  { id: "seizure",           label: "Seizure",            icon: "⚡", color: "#E17055" },
  { id: "allergic_reaction", label: "Allergic Reaction",  icon: "🌿", color: "#00B894" },
  { id: "spinal_injury",     label: "Spinal Injury",      icon: "🦴", color: "#636E72" },
  { id: "heart_failure",     label: "Heart Failure",      icon: "💔", color: "#D63031" },
  // FIX: Bug #6 — 5 conditions existed in CONDITION_EQUIPMENT but were not selectable in the UI
  { id: "fracture",          label: "Fracture",           icon: "🦴", color: "#795548" },
  { id: "snake_bite",        label: "Snake Bite",         icon: "🐍", color: "#4CAF50" },
  { id: "drowning",          label: "Drowning",           icon: "💧", color: "#0288D1" },
  { id: "electrocution",     label: "Electrocution",      icon: "⚡", color: "#FFC107" },
  { id: "liver_failure",     label: "Liver Failure",      icon: "🫀", color: "#8D6E63" },
];

const SEVERITY_LEVELS = [
  { value: 1, label: "Low",      color: "#17B86B", bg: "#E8FDF4" },
  { value: 2, label: "Moderate", color: "#FFB21A", bg: "#FFF8E8" },
  { value: 3, label: "High",     color: "#FF6B35", bg: "#FFF3EE" },
  { value: 4, label: "Critical", color: "#EE3B3B", bg: "#FFF0F0" },
];

// FIX: Filter out internal fallback notes — never show "Rule-based assessment (AI offline)" to user
function isInternalNote(text) {
  if (!text) return false;
  const t = text.toLowerCase();
  return t.includes("rule-based assessment") ||
         t.includes("ai offline") ||
         t.includes("(ai offline)");
}

async function analyzeWithAI(voiceText) {
  try {
    const res = await api.post("/api/ai/equipment-recommend", { voice_text: voiceText });
    return res.data;
  } catch {
    return null;
  }
}

function VoicePulse({ active }) {
  return (
    <div className="flex items-center gap-[3px] h-6">
      {[0, 1, 2, 3, 4].map(i => (
        <div key={i} className="w-[3px] rounded-sm transition-all duration-150" style={{
          background: active ? "#1A78F2" : "#D0D5E8",
          height: active ? `${[10, 18, 24, 16, 8][i]}px` : "6px",
          animation: active ? `pulse_${i} 0.8s ease-in-out ${i * 0.1}s infinite alternate` : "none",
        }} />
      ))}
      <style>{`
        @keyframes pulse_0 { from{height:8px} to{height:14px} }
        @keyframes pulse_1 { from{height:14px} to{height:22px} }
        @keyframes pulse_2 { from{height:20px} to{height:28px} }
        @keyframes pulse_3 { from{height:12px} to{height:20px} }
        @keyframes pulse_4 { from{height:6px} to{height:12px} }
      `}</style>
    </div>
  );
}

export default function Dispatch() {
  const navigate = useNavigate();

  const [selectedCondition, setSelectedCondition] = useState(null);
  const [checkedEquipment, setCheckedEquipment] = useState([]);
  const [notes, setNotes] = useState("");
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [gpsLabel, setGpsLabel] = useState("Acquiring GPS...");
  const [gpsReady, setGpsReady] = useState(false);

  const [isListening, setIsListening] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [showVoicePanel, setShowVoicePanel] = useState(false);
  const [aiSuggestedItems, setAiSuggestedItems] = useState([]);
  // FIX: Track whether AI result is from real Claude or rule-based fallback
  const [aiIsRealResult, setAiIsRealResult] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLat(30.3165); setLng(78.0322);
      setGpsLabel("Dehradun, Uttarakhand (default)");
      setGpsReady(true); return;
    }
    navigator.geolocation.getCurrentPosition(
      pos => {
        setLat(pos.coords.latitude); setLng(pos.coords.longitude);
        setGpsLabel(`${pos.coords.latitude.toFixed(4)}°N  ${pos.coords.longitude.toFixed(4)}°E`);
        setGpsReady(true);
      },
      () => {
        setLat(30.3165); setLng(78.0322);
        setGpsLabel("Dehradun, Uttarakhand (default)");
        setGpsReady(true);
      },
      { enableHighAccuracy: true }
    );
  }, []);

  useEffect(() => {
    if (selectedCondition) {
      const base = CONDITION_EQUIPMENT[selectedCondition] || [];
      setCheckedEquipment(base);
      setAiSuggestedItems([]);
    }
  }, [selectedCondition]);

  const startListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { setVoiceError("Voice input not supported. Use Chrome or Edge."); return; }
    const recognition = new SR();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-IN";
    recognition.onresult = (e) => {
      setVoiceTranscript(Array.from(e.results).map(r => r[0].transcript).join(" "));
    };
    recognition.onerror = (e) => {
      setVoiceError(e.error === "not-allowed"
        ? "Microphone access denied. Please allow mic permissions."
        : `Voice error: ${e.error}`);
      setIsListening(false);
    };
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
    setVoiceError("");
    setVoiceTranscript("");
    setAiResult(null);
    setAiIsRealResult(false);
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  const analyzeVoice = useCallback(async () => {
    if (!voiceTranscript.trim()) return;
    setIsAnalyzing(true);
    setError("");
    const result = await analyzeWithAI(voiceTranscript);

    if (result) {
      if (result.low_confidence) {
        setVoiceError("No medical condition detected. Please re-describe the emergency.");
        setAiResult(null);
        setIsAnalyzing(false);
        return;
      }
      setAiResult(result);

      // FIX: Only set notes if it's a real AI note, not the internal fallback message
      if (result.notes && !isInternalNote(result.notes)) {
        setNotes(result.notes);
      }
      // FIX: Detect if this is real AI or rule-based fallback
      const isReal = !isInternalNote(result.notes || "");
      setAiIsRealResult(isReal);

      if (result.matched_condition_id && result.matched_condition_id !== "other") {
        setSelectedCondition(result.matched_condition_id);
      }

      if (result.recommended_equipment?.length) {
        const baseEquip = result.matched_condition_id !== "other"
          ? (CONDITION_EQUIPMENT[result.matched_condition_id] || [])
          : [];
        const normalizeMap = {
          "defibrillator": "defibrillator", "ventilator": "ventilator",
          "ecg monitor": "ecg", "ecg": "ecg", "ct scan": "ct_scan",
          "ct scan access": "ct_scan", "blood bank": "blood_bank",
          "blood bags": "blood_bank", "icu equipment": "icu_equipment",
          "oxygen": "ventilator", "oxygen cylinder": "ventilator",
        };
        const normalized = result.recommended_equipment
          .map(e => normalizeMap[e.toLowerCase()] || null)
          .filter(e => e && ALL_EQUIPMENT.includes(e));
        const aiExtra = normalized.filter(e => !baseEquip.includes(e));
        const merged = [...new Set([...baseEquip, ...normalized])];
        setCheckedEquipment(merged);
        setAiSuggestedItems(aiExtra);
      }
    } else {
      // Complete failure — don't pollute notes, just show error
      setError("Could not analyze voice. Please select condition manually.");
    }
    setIsAnalyzing(false);
  }, [voiceTranscript]);

  const toggleEquipment = (item) => {
    setCheckedEquipment(prev =>
      prev.includes(item) ? prev.filter(e => e !== item) : [...prev, item]
    );
  };

  const handleSubmit = async () => {
    if (!selectedCondition) { setError("Please select a patient condition."); return; }
    setLoading(true); setError("");
    try {
      const res = await api.post("/api/dispatch/", {
        condition: selectedCondition,
        custom_condition: aiResult?.condition_label || null,
        equipment_needed: checkedEquipment,
        ambulance_lat: lat,
        ambulance_lng: lng,
        // FIX: Only send notes if they're real (not internal fallback text)
        notes: (notes && !isInternalNote(notes)) ? notes : null,
      });
      // Pass full enriched response — Result.jsx reads selected_hospital, alternatives, etc.
      navigate("/result", { state: { result: res.data, ambLat: lat, ambLng: lng } });
    } catch (e) {
      setError(e.response?.data?.detail || "Dispatch failed. Please try again.");
    } finally { setLoading(false); }
  };

  const currentSeverityObj = aiResult
    ? SEVERITY_LEVELS.find(s => s.value === aiResult.severity)
    : null;

  return (
    <div className="min-h-screen bg-[#F7F7FC] font-['Inter',sans-serif] pb-10">

      {/* Nav */}
      <nav className="glass-panel sticky top-0 z-50 h-16 flex items-center px-8 mb-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative w-9 h-9 bg-[#EE3B3B] rounded-lg flex items-center justify-center">
            <div className="absolute w-4 h-1.5 bg-white rounded-sm" />
            <div className="absolute w-1.5 h-4 bg-white rounded-sm" />
          </div>
          <div>
            <p className="text-[16px] font-bold premium-gradient-text leading-none">MediRoute</p>
            <p className="text-[11px] text-[#737A8F]">Premium Dispatch</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-medium ${gpsReady ? "bg-[#E8FDF2] text-[#17B86B]" : "bg-[#FFF8E0] text-[#FFB21A]"}`}>
          <span className={`w-2 h-2 rounded-full ${gpsReady ? "bg-[#17B86B]" : "bg-[#FFB21A]"}`} />
          {gpsReady ? "GPS Active" : "GPS Acquiring..."}
        </div>
      </nav>

      <div className="max-w-[960px] mx-auto px-8 py-8">

        {/* VOICE PANEL */}
        <div className={`glass-card rounded-xl border-[1.5px] p-5 mb-6 transition-all ${showVoicePanel ? "bg-white/80 border-[#1A78F2] shadow-[0_4px_20px_rgba(26,120,242,0.15)]" : "border-transparent"}`}>
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[16px]">🎙️</span>
                <span className="font-semibold text-[15px] text-[#1A1E2E]">Describe Emergency by Voice</span>
                <span className="text-[11px] bg-[#1A78F2] text-white rounded px-[7px] py-[2px] font-medium">NEW</span>
              </div>
              <p className="text-[13px] text-[#737A8F]">Speak the patient's condition — AI auto-detects severity & recommends equipment</p>
            </div>
            <button
              onClick={() => setShowVoicePanel(v => !v)}
              className={`px-[18px] py-2 rounded-lg border-[1.5px] text-[13px] font-medium cursor-pointer transition-all ${showVoicePanel ? "bg-[#1A78F2] border-[#1A78F2] text-white" : "bg-white border-[#D0D5E8] text-[#1A1E2E] hover:border-[#1A78F2]"}`}
            >
              {showVoicePanel ? "Close" : "Open Voice Input"}
            </button>
          </div>

          {showVoicePanel && (
            <div className="mt-5">
              <div className="flex items-center gap-4 mb-4">
                <button
                  onClick={isListening ? stopListening : startListening}
                  className="w-[52px] h-[52px] rounded-full border-none text-white text-[20px] cursor-pointer flex items-center justify-center flex-shrink-0 transition-all"
                  style={{
                    background: isListening ? "#EE3B3B" : "#1A78F2",
                    boxShadow: isListening ? "0 0 0 6px rgba(238,59,59,0.15)" : "none",
                  }}
                >
                  {isListening ? "⏹" : "🎙"}
                </button>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <VoicePulse active={isListening} />
                    <span className={`text-[12px] ${isListening ? "text-[#1A78F2] font-medium" : "text-[#737A8F]"}`}>
                      {isListening ? "Listening… speak now" : "Press mic to start"}
                    </span>
                  </div>
                  {voiceTranscript && (
                    <div className="bg-white border border-[#D0D5E8] rounded-lg px-[14px] py-[10px] text-[14px] text-[#1A1E2E] italic leading-relaxed">
                      "{voiceTranscript}"
                    </div>
                  )}
                  {voiceError && <p className="mt-1.5 text-[12px] text-[#EE3B3B]">⚠ {voiceError}</p>}
                </div>
              </div>

              {voiceTranscript && !isListening && (
                <button
                  onClick={analyzeVoice}
                  disabled={isAnalyzing}
                  className="w-full py-[11px] rounded-lg border-none text-white text-[14px] font-semibold flex items-center justify-center gap-2 transition-colors"
                  style={{ background: isAnalyzing ? "#8FB8F6" : "#1A78F2", cursor: isAnalyzing ? "not-allowed" : "pointer" }}
                >
                  {isAnalyzing ? (
                    <><span className="w-[14px] h-[14px] border-2 border-white/40 border-t-white rounded-full inline-block animate-spin" /> AI Analyzing…</>
                  ) : "✨ Analyze with AI & Get Equipment Recommendations"}
                </button>
              )}

              {aiResult && (
                <div className="mt-4 bg-white border-[1.5px] border-[#17B86B] rounded-[10px] p-4">
                  <div className="flex items-center gap-1.5 mb-3">
                    <span className="text-[14px]">✅</span>
                    <span className="font-semibold text-[#17B86B] text-[14px]">
                      {/* FIX: Show "AI Analysis" vs "Smart Detection" depending on source */}
                      {aiIsRealResult ? "AI Analysis Complete" : "Smart Detection Complete"}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-3 mb-3">
                    <div className="bg-[#F7F7FC] rounded-lg px-3 py-2">
                      <div className="text-[11px] text-[#737A8F] mb-1">Condition detected</div>
                      <div className="font-semibold text-[13px] text-[#1A1E2E]">{aiResult.condition_label}</div>
                    </div>
                    <div className="rounded-lg px-3 py-2" style={{ background: currentSeverityObj?.bg || "#F7F7FC" }}>
                      <div className="text-[11px] text-[#737A8F] mb-1">Severity</div>
                      <div className="font-bold text-[13px]" style={{ color: currentSeverityObj?.color || "#1A1E2E" }}>
                        {aiResult.severity_label} (Level {aiResult.severity})
                      </div>
                    </div>
                  </div>
                  {/* FIX: Only show hospital note if it's a real note, never show internal fallback text */}
                  {aiResult.notes && !isInternalNote(aiResult.notes) && (
                    <div className="bg-[#FFFBEB] border border-[#FFE082] rounded-lg px-3 py-2 text-[13px] text-[#7A5C00]">
                      <strong>Hospital note:</strong> {aiResult.notes}
                    </div>
                  )}
                  {/* FIX: Show equipment that was auto-selected so user knows what happened */}
                  {checkedEquipment.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-[#E8F5E9]">
                      <div className="text-[11px] text-[#737A8F] mb-2">Equipment auto-selected based on condition:</div>
                      <div className="flex flex-wrap gap-1.5">
                        {checkedEquipment.map(eq => (
                          <span key={eq} className="text-[11px] bg-[#EBF3FF] text-[#1A78F2] border border-[#BDD6FF] rounded px-2 py-0.5 font-medium">
                            ✓ {EQUIPMENT_LABELS[eq] || eq}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center gap-3 mb-5">
          <div className="flex-1 h-px bg-[#E2E6F0]" />
          <span className="text-[12px] text-[#9EA6BC] font-medium">OR SELECT CONDITION MANUALLY</span>
          <div className="flex-1 h-px bg-[#E2E6F0]" />
        </div>

        {/* CONDITION GRID */}
        <div className="glass-card rounded-xl p-5 mb-6">
          <h3 className="text-[13px] font-semibold text-[#404454] uppercase tracking-wider mb-4">Patient Condition</h3>
          <div className="grid grid-cols-5 gap-3">
            {CONDITIONS.map(c => (
              <button
                key={c.id}
                onClick={() => setSelectedCondition(prev => prev === c.id ? null : c.id)}
                className="py-3 px-2 rounded-[10px] border-[1.5px] cursor-pointer transition-all text-center"
                style={{
                  borderColor: selectedCondition === c.id ? c.color : "#E2E6F0",
                  background: selectedCondition === c.id ? `${c.color}15` : "#FAFBFF",
                }}
              >
                <div className="text-[22px] mb-1.5">{c.icon}</div>
                <div className="text-[11px] leading-tight" style={{
                  fontWeight: selectedCondition === c.id ? 600 : 400,
                  color: selectedCondition === c.id ? c.color : "#4A5068",
                }}>{c.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* EQUIPMENT PANEL */}
        {(selectedCondition || aiResult) && (
          <div className="glass-card border-[1.5px] border-[#1A78F2]/50 shadow-[0_4px_20px_rgba(26,120,242,0.1)] rounded-xl p-5 mb-6 animate-[fadeIn_0.3s_ease]">
            <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}`}</style>
            <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-[14px]">🧰</span>
                <div>
                  <div className="font-semibold text-[14px] text-[#1A1E2E]">Recommended Equipment</div>
                  <div className="text-[12px] text-[#737A8F]">
                    {aiSuggestedItems.length > 0
                      ? `Condition defaults + ${aiSuggestedItems.length} AI additions`
                      : `Auto-suggested for ${CONDITIONS.find(c => c.id === selectedCondition)?.label || "condition"}`}
                  </div>
                </div>
              </div>
              <span className="text-[12px] text-[#737A8F] bg-[#F7F7FC] border border-[#E2E6F0] rounded-md px-[10px] py-1">
                {checkedEquipment.length} selected
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {ALL_EQUIPMENT.map(item => {
                const isChecked = checkedEquipment.includes(item);
                const isAI = aiSuggestedItems.includes(item);
                return (
                  <button
                    key={item}
                    onClick={() => toggleEquipment(item)}
                    className="flex items-center gap-2 px-[14px] py-2 rounded-lg border-[1.5px] cursor-pointer transition-all text-[13px]"
                    style={{
                      borderColor: isChecked ? "#1A78F2" : "#E2E6F0",
                      background: isChecked ? "#EBF3FF" : "#FAFBFF",
                      color: isChecked ? "#1A78F2" : "#4A5068",
                      fontWeight: isChecked ? 500 : 400,
                    }}
                  >
                    <span className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border-[1.5px] transition-all"
                      style={{
                        borderColor: isChecked ? "#1A78F2" : "#C5CBDC",
                        background: isChecked ? "#1A78F2" : "transparent",
                      }}
                    >
                      {isChecked && <span className="text-white text-[10px]">✓</span>}
                    </span>
                    {EQUIPMENT_LABELS[item]}
                    {isAI && (
                      <span className="text-[10px] bg-[#F0F7FF] text-[#1A78F2] border border-[#BDD6FF] rounded px-[5px] py-px font-medium ml-0.5">AI</span>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="mt-3 p-3 bg-[#F7F7FC] rounded-lg text-[12px] text-[#737A8F]">
              ℹ️ Toggle equipment to match what's needed. This helps the ML engine find the best-equipped hospital.
            </div>
          </div>
        )}

        {/* NOTES */}
        <div className="bg-white border border-[#F0F2F7] rounded-xl p-5 mb-6">
          <label className="text-[12px] text-[#737A8F] block mb-2">Additional Notes (optional)</label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Any critical details for the hospital…"
            rows={2}
            className="w-full px-3 py-2 border border-[#E2E6F0] rounded-lg text-[13px] outline-none resize-vertical text-[#1A1E2E] leading-relaxed"
          />
        </div>

        {error && (
          <div className="bg-[#FFF0F0] border border-[#FFCDD2] rounded-lg px-4 py-3 text-[#EE3B3B] text-[13px] mb-4 flex items-center gap-2">
            ⚠ {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading || !gpsReady}
          className="w-full h-[60px] bg-gradient-to-r from-[#EE3B3B] to-[#FF6B35] hover:to-[#EE3B3B] disabled:opacity-60 text-white font-bold text-[16px] rounded-xl shadow-[0_8px_20px_rgba(238,59,59,0.25)] transition-all flex items-center justify-center gap-3 transform hover:-translate-y-1"
        >
          {loading
            ? <><span className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" /> Scanning 188 hospitals...</>
            : "🚑  Dispatch Emergency — Find Best Hospital"
          }
        </button>
        <p className="text-center text-[12px] text-[#9EA6BC] mt-2.5">
          ML engine will score all 188 hospitals across Uttarakhand in real-time
        </p>
      </div>
    </div>
  );
}
```

<hr>

## 3. frontend/src/pages/Result.jsx

```jsx
/**
 * Result.jsx — Enriched dispatch result page.
 *
 * Consumes the new DispatchResponse shape:
 *   selected_hospital  { score, score_breakdown, explanation, pros, cons, ... }
 *   alternatives       [ ScoredHospitalResponse, ... ]
 *   rejected_hospitals { missing_equipment, insufficient_beds, too_far, total_rejected }
 *   no_match           bool
 *   no_match_reason    string
 *   fallback_options   string[]
 *   triage             { condition, severity, required_equipment }
 *
 * Legacy flat fields (hospital_id, hospital_name, distance_km, etc.) are still
 * present in the response and used for map navigation — no Map.jsx changes needed.
 */

import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import CaseTimeline from "../components/CaseTimeline";

// ── Severity badge config (mirrors backend severity.py) ──────────────────────
const SEVERITY_BADGE = {
  critical: { label: "CRITICAL", bg: "#7f1d1d", text: "#fecaca", border: "#ef4444", dot: "#f87171" },
  moderate: { label: "MODERATE", bg: "#78350f", text: "#fef3c7", border: "#f59e0b", dot: "#fbbf24" },
  low:      { label: "LOW",      bg: "#14532d", text: "#dcfce7", border: "#22c55e", dot: "#4ade80" },
};

// ── Sub-score color bands ────────────────────────────────────────────────────
function scoreColor(v) {
  if (v >= 0.75) return "#4ade80";
  if (v >= 0.50) return "#fbbf24";
  if (v >= 0.25) return "#f97316";
  return "#f87171";
}

// ── Score ring (SVG arc) ─────────────────────────────────────────────────────
function ScoreRing({ value, size = 72, label }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const filled = circ * value;
  const color = scoreColor(value);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1e293b" strokeWidth={7} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={color}
          strokeWidth={7}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)" }}
        />
        <text
          x={size / 2} y={size / 2 + 1}
          textAnchor="middle" dominantBaseline="middle"
          style={{
            fill: color, fontSize: size * 0.22, fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 700, transform: "rotate(90deg)",
            transformOrigin: `${size / 2}px ${size / 2}px`,
          }}
        >
          {Math.round(value * 100)}
        </text>
      </svg>
      <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "monospace" }}>
        {label}
      </span>
    </div>
  );
}

// ── Chip ─────────────────────────────────────────────────────────────────────
function Chip({ text, positive }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: 20,
      fontSize: 12, fontWeight: 500,
      background: positive ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)",
      border: `1px solid ${positive ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.25)"}`,
      color: positive ? "#86efac" : "#fca5a5",
    }}>
      <span style={{ fontSize: 8 }}>{positive ? "▲" : "▼"}</span>
      {text}
    </span>
  );
}

// ── Alternative hospital card ──────
function AlternativeCard({ hospital, onOverride, index }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{
      background: "rgba(15,23,42,0.6)", border: "1px solid #1e293b",
      borderRadius: 10, padding: "14px 16px",
      display: "flex", flexDirection: "column", gap: 8,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: 11, color: "#475569", marginRight: 8 }}>ALT {index + 1}</span>
          <span style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 14 }}>{hospital.name}</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: scoreColor(hospital.score), fontFamily: "monospace", fontWeight: 700 }}>
            {Math.round(hospital.score * 100)}
          </span>
          <button
            onClick={() => setExpanded(e => !e)}
            style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 12 }}
          >
            {expanded ? "▲" : "▼"}
          </button>
          <button
            onClick={() => onOverride(hospital)}
            style={{
              padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600,
              background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.3)",
              color: "#fbbf24", cursor: "pointer",
            }}
          >
            OVERRIDE →
          </button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#64748b" }}>
        <span>📍 {hospital.distance_km} km</span>
        <span>🛏 {hospital.available_beds} beds</span>
        <span>⏱ {hospital.eta_minutes} min</span>
      </div>
      {expanded && (
        <div style={{ borderTop: "1px solid #1e293b", paddingTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {hospital.pros?.map((p, i) => <Chip key={i} text={p} positive />)}
            {hospital.cons?.map((c, i) => <Chip key={i} text={c} positive={false} />)}
          </div>
          <div style={{ fontSize: 11, color: "#475569" }}>
            {hospital.explanation?.join(" ")}
          </div>
        </div>
      )}
    </div>
  );
}

// ── No-match state ────────────────────────────────────────────────────────────
function NoMatchView({ result, onNewDispatch }) {
  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "40px 20px", fontFamily: "system-ui, sans-serif" }}>
      <div style={{
        background: "rgba(127,29,29,0.15)", border: "1px solid rgba(239,68,68,0.3)",
        borderRadius: 12, padding: 24, textAlign: "center", marginBottom: 24,
      }}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
        <div style={{ color: "#fca5a5", fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
          No Eligible Hospital Found
        </div>
        <div style={{ color: "#94a3b8", fontSize: 13, lineHeight: 1.6 }}>
          {result.no_match_reason}
        </div>
      </div>

      {result.rejected_hospitals && (
        <div style={{
          background: "rgba(15,23,42,0.8)", border: "1px solid #1e293b",
          borderRadius: 10, padding: 16, marginBottom: 20,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
            Rejection Breakdown
          </div>
          {[
            ["Missing equipment", result.rejected_hospitals.missing_equipment],
            ["Insufficient beds", result.rejected_hospitals.insufficient_beds],
            ["Too far", result.rejected_hospitals.too_far],
          ].map(([label, count]) => count > 0 && (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #0f172a" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>{label}</span>
              <span style={{ color: "#f87171", fontFamily: "monospace", fontWeight: 700 }}>{count}</span>
            </div>
          ))}
        </div>
      )}

      {result.fallback_options?.length > 0 && (
        <div style={{
          background: "rgba(15,23,42,0.8)", border: "1px solid #1e293b",
          borderRadius: 10, padding: 16, marginBottom: 20,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
            Nearest Hospitals (Equipment Not Guaranteed)
          </div>
          {result.fallback_options.map((opt, i) => (
            <div key={i} style={{ color: "#94a3b8", fontSize: 13, padding: "5px 0", borderBottom: "1px solid #0f172a" }}>
              {opt}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onNewDispatch}
        style={{
          width: "100%", padding: "12px 0", borderRadius: 8, fontSize: 14,
          fontWeight: 700, background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)",
          color: "#f87171", cursor: "pointer",
        }}
      >
        ← NEW DISPATCH
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Result() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const result = state?.result;

  const [mounted, setMounted] = useState(false);
  useEffect(() => { setTimeout(() => setMounted(true), 50); }, []);

  if (!result) {
    return (
      <div style={{ padding: 40, color: "#94a3b8", textAlign: "center" }}>
        No dispatch result found.{" "}
        <button onClick={() => navigate("/dispatch")} style={{ color: "#60a5fa", background: "none", border: "none", cursor: "pointer" }}>
          Return to Dispatch
        </button>
      </div>
    );
  }

  if (result.no_match) {
    return <NoMatchView result={result} onNewDispatch={() => navigate("/dispatch")} />;
  }

  const sh = result.selected_hospital;
  const triage = result.triage || {};
  const severity = (triage.severity || "moderate").toLowerCase();
  const badge = SEVERITY_BADGE[severity] || SEVERITY_BADGE.moderate;
  const breakdown = sh?.score_breakdown || {};
  const decisionType = result.decision_type || triage.decision_type || "direct";
  const isStabilizeFirst = decisionType === "stabilize_first";
  const routePrimary = result.primary_destination || sh;
  const routeSecondary = result.secondary_destination;
  const routingReasoning = result.reasoning || {};
  const stabilityScore = Number(routingReasoning.stability_score || 0);
  const diversionReasons = [
    ...(routingReasoning.missing_equipment || []).map((item) => `Missing ambulance equipment: ${item}`),
    ...(routingReasoning.vitals_flags || []).map((flag) => `Critical vitals flag: ${flag.replaceAll("_", " ")}`),
  ];
  const diversionText = diversionReasons.length > 0
    ? diversionReasons.join("; ")
    : "Stability constraints required immediate stabilization before final transfer.";

  const destinationName = (destination) => destination?.name || destination?.hospital_name || "Unknown";
  const destinationEta = (destination) => destination?.eta_minutes ?? "-";
  const destinationDistance = (destination) => destination?.distance_km ?? "-";

  const handleOverride = (altHospital) => {
    navigate("/map", {
      state: {
        ...state,
        result: {
          ...result,
          hospital_id: altHospital.hospital_id,
          hospital_name: altHospital.name,
          distance_km: altHospital.distance_km,
          eta_minutes: altHospital.eta_minutes,
          hospital_lat: altHospital.hospital_lat,
          hospital_lng: altHospital.hospital_lng,
          address: altHospital.address,
          selected_hospital: altHospital,
          overridden: true,
        },
      },
    });
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060d1a",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      color: "#e2e8f0",
    }}>
      {/* ── Top bar ── */}
      <div className="sticky top-0 z-50 flex justify-between items-center px-6 py-3 border-b border-[#0f172a] bg-[#060d1a]/80 backdrop-blur-md">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#f87171", fontSize: 16 }}>🚑</span>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", color: "#94a3b8" }}>
            MEDIROUTE / DISPATCH RESULT
          </span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => navigate("/map", { state })}
            className="px-4 py-1.5 rounded-md text-[11px] font-bold tracking-wider text-[#60a5fa] bg-blue-500/10 border border-blue-500/25 hover:bg-blue-500/20 transition-all flex items-center gap-1"
          >
            VIEW MAP →
          </button>
          <button
            onClick={() => navigate("/dispatch")}
            className="px-4 py-1.5 rounded-md text-[11px] font-bold tracking-wider text-[#94a3b8] bg-slate-500/10 border border-[#1e293b] hover:bg-slate-500/20 transition-all"
          >
            NEW DISPATCH
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "28px 20px" }}>

        {/* ── Severity + hospital header ── */}
        <div 
          className="flex justify-between items-start flex-wrap gap-4 mb-5 p-6 rounded-2xl border border-[#1e293b] bg-slate-900/50 backdrop-blur-sm shadow-xl"
          style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.4s ease",
          }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span style={{
                padding: "3px 12px", borderRadius: 20, fontSize: 11, fontWeight: 800,
                letterSpacing: "0.1em",
                background: badge.bg, color: badge.text, border: `1px solid ${badge.border}`,
              }}>
                {badge.label}
              </span>
              <span style={{ color: "#475569", fontSize: 12 }}>{triage.condition}</span>
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#f1f5f9", marginBottom: 4 }}>
              {sh?.name}
            </div>
            <div style={{ fontSize: 12, color: "#475569" }}>{sh?.address || "Address not available"}</div>
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#60a5fa" }}>{sh?.distance_km} km</div>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.08em" }}>DISTANCE</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#34d399" }}>{sh?.eta_minutes} min</div>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.08em" }}>ETA</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#a78bfa" }}>{sh?.available_beds}</div>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.08em" }}>BEDS</div>
            </div>
          </div>
        </div>

        {/* ── Two-hop route (stabilize first only) ── */}
        {isStabilizeFirst && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.45s ease 0.06s",
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px", marginBottom: 20,
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase" }}>
              Two-Step Route
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div style={{ background: "rgba(10,15,30,0.6)", border: "1px solid #1e293b", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 11, color: "#fbbf24", marginBottom: 6, letterSpacing: "0.08em" }}>STEP 1: STABILIZATION HOSPITAL</div>
                <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: 4 }}>{destinationName(routePrimary)}</div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>ETA: {destinationEta(routePrimary)} min</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>Distance: {destinationDistance(routePrimary)} km</div>
              </div>
              <div style={{ background: "rgba(10,15,30,0.6)", border: "1px solid #1e293b", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 11, color: "#60a5fa", marginBottom: 6, letterSpacing: "0.08em" }}>STEP 2: FINAL HOSPITAL</div>
                <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: 4 }}>{destinationName(routeSecondary)}</div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>ETA: {destinationEta(routeSecondary)} min</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>Distance: {destinationDistance(routeSecondary)} km</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap", fontSize: 12 }}>
              <span style={{ color: "#93c5fd" }}>
                Stability Score: <strong style={{ color: scoreColor(stabilityScore) }}>{Math.round(stabilityScore * 100)}%</strong>
              </span>
              <span style={{ color: "#fca5a5" }}>Reason for diversion: {diversionText}</span>
            </div>
          </div>
        )}

        {/* ── Score breakdown rings ── */}
        <div style={{
          opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.5s ease 0.1s",
          background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
          borderRadius: 14, padding: "20px 24px", marginBottom: 20,
        }}>
          <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 16, textTransform: "uppercase" }}>
            Score Breakdown
          </div>
          <div style={{ display: "flex", justifyContent: "space-around", flexWrap: "wrap", gap: 16 }}>
            <ScoreRing value={breakdown.distance  ?? 0} label="Distance"   />
            <ScoreRing value={breakdown.beds       ?? 0} label="Capacity"   />
            <ScoreRing value={breakdown.specialist ?? 0} label="Specialist" />
            <ScoreRing value={breakdown.equipment  ?? 1} label="Equipment"  />
            <ScoreRing value={sh?.score ?? 0} size={88}  label="Overall"    />
          </div>
        </div>

        {/* ── Explanation + pros/cons ── */}
        <div style={{
          opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.5s ease 0.18s",
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20,
        }}>
          {/* Explanation */}
          <div style={{
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px",
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase" }}>
              Reasoning
            </div>
            {(sh?.explanation || []).map((line, i) => (
              <div key={i} style={{
                fontSize: 12, color: "#94a3b8", lineHeight: 1.7,
                paddingBottom: 6, borderBottom: i < (sh.explanation.length - 1) ? "1px solid #0f172a" : "none",
                marginBottom: 6,
              }}>
                {line}
              </div>
            ))}
          </div>

          {/* Pros / Cons */}
          <div style={{
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px",
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase" }}>
              Pros / Cons
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(sh?.pros || []).map((p, i) => <Chip key={`p-${i}`} text={p} positive />)}
              {(sh?.cons || []).map((c, i) => <Chip key={`c-${i}`} text={c} positive={false} />)}
            </div>
          </div>
        </div>

        {/* ── Alternatives ── */}
        {result.alternatives?.length > 0 && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.26s",
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px", marginBottom: 20,
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 14, textTransform: "uppercase" }}>
              Alternative Hospitals
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {result.alternatives.map((alt, i) => (
                <AlternativeCard
                  key={alt.hospital_id}
                  hospital={alt}
                  index={i}
                  onOverride={handleOverride}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Rejection stats ── */}
        {result.rejected_hospitals?.total_rejected > 0 && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.32s",
            background: "rgba(15,23,42,0.5)", border: "1px solid #0f172a",
            borderRadius: 10, padding: "12px 18px", marginBottom: 20,
            display: "flex", gap: 24, flexWrap: "wrap",
          }}>
            <div style={{ fontSize: 10, color: "#334155", letterSpacing: "0.1em", textTransform: "uppercase", alignSelf: "center" }}>
              Filtered out:
            </div>
            {result.rejected_hospitals.missing_equipment > 0 && (
               <span style={{ fontSize: 12, color: "#475569" }}>
                <span style={{ color: "#f87171", fontWeight: 700 }}>{result.rejected_hospitals.missing_equipment}</span> missing equipment
              </span>
            )}
            {result.rejected_hospitals.insufficient_beds > 0 && (
              <span style={{ fontSize: 12, color: "#475569" }}>
                <span style={{ color: "#f87171", fontWeight: 700 }}>{result.rejected_hospitals.insufficient_beds}</span> insufficient beds
              </span>
            )}
            {result.rejected_hospitals.too_far > 0 && (
              <span style={{ fontSize: 12, color: "#475569" }}>
                <span style={{ color: "#f87171", fontWeight: 700 }}>{result.rejected_hospitals.too_far}</span> too far
              </span>
            )}
            <span style={{ fontSize: 12, color: "#334155", marginLeft: "auto" }}>
              {result.rejected_hospitals.total_evaluated} evaluated
            </span>
          </div>
        )}

        {/* ── Case timeline ── */}
        {result.case_id && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.38s",
          }}>
            <CaseTimeline caseId={result.case_id} />
          </div>
        )}

        {/* ── Data source footer ── */}
        <div style={{
          marginTop: 20, padding: "10px 0",
          borderTop: "1px solid #0f172a",
          display: "flex", justifyContent: "space-between",
          fontSize: 10, color: "#334155",
        }}>
          <span>DATA SOURCE: {sh?.data_source?.toUpperCase() || "LIVE"}</span>
          <span>LAST UPDATED: {sh?.last_updated ? new Date(sh.last_updated).toLocaleTimeString() : "—"}</span>
        </div>
      </div>
    </div>
  );
}
```
