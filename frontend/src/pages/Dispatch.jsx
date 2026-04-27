// frontend/src/pages/Dispatch.jsx
import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import RouteFallback from "../components/RouteFallback";
import useCaseSocket from "../hooks/useCaseSocket";

const VoiceInput = lazy(() => import("../components/VoiceInput"));
const CaseChat = lazy(() => import("../components/CaseChat"));
const CallPanel = lazy(() => import("../components/CallPanel"));

const CONDITION_EQUIPMENT = {
  cardiac_arrest: ["defibrillator", "ventilator", "ecg", "blood_bank", "icu_equipment"],
  chest_pain: ["ecg", "ventilator", "blood_bank"],
  stroke: ["ct_scan", "ventilator", "blood_bank", "icu_equipment"],
  trauma: ["blood_bank", "ventilator", "icu_equipment", "ct_scan"],
  respiratory: ["ventilator", "icu_equipment"],
  burns: ["ventilator", "blood_bank", "icu_equipment"],
  poisoning: ["ventilator", "icu_equipment"],
  obstetric: ["blood_bank", "ventilator", "icu_equipment"],
  pediatric: ["ventilator", "icu_equipment"],
  diabetic: ["blood_bank", "icu_equipment"],
  fracture: ["ct_scan"],
  snake_bite: ["blood_bank", "ventilator"],
  drowning: ["ventilator", "icu_equipment", "defibrillator"],
  electrocution: ["defibrillator", "ventilator", "ecg"],
  seizure: ["ventilator", "ct_scan", "icu_equipment"],
  allergic_reaction: ["ventilator"],
  heart_failure: ["defibrillator", "ecg", "ventilator", "icu_equipment", "blood_bank"],
  kidney_failure: ["ventilator", "blood_bank", "icu_equipment"],
  liver_failure: ["blood_bank", "ventilator", "icu_equipment"],
  spinal_injury: ["ct_scan", "ventilator", "icu_equipment"],
};

const EQUIPMENT_LABELS = {
  defibrillator: "Defibrillator",
  ventilator: "Ventilator",
  ecg: "ECG Monitor",
  ct_scan: "CT Scan",
  blood_bank: "Blood Bank",
  icu_equipment: "ICU Equipment",
};

const ALL_EQUIPMENT = Object.keys(EQUIPMENT_LABELS);

const CONDITIONS = [
  { id: "cardiac_arrest", label: "Cardiac Arrest", icon: "♥", color: "#EE3B3B" },
  { id: "chest_pain", label: "Chest Pain", icon: "⚡", color: "#FF6B35" },
  { id: "stroke", label: "Stroke / TIA", icon: "🧠", color: "#9B59B6" },
  { id: "trauma", label: "Trauma / Injury", icon: "🩹", color: "#E67E22" },
  { id: "respiratory", label: "Respiratory", icon: "💨", color: "#3498DB" },
  { id: "burns", label: "Burns", icon: "🔥", color: "#E74C3C" },
  { id: "poisoning", label: "Poisoning / OD", icon: "☠", color: "#2ECC71" },
  { id: "obstetric", label: "Obstetric", icon: "🤰", color: "#E91E8C" },
  { id: "pediatric", label: "Pediatric", icon: "👶", color: "#00BCD4" },
  { id: "diabetic", label: "Diabetic Emergency", icon: "💉", color: "#FF9800" },
  { id: "kidney_failure", label: "Kidney Failure", icon: "🫘", color: "#6C5CE7" },
  { id: "seizure", label: "Seizure", icon: "⚡", color: "#E17055" },
  { id: "allergic_reaction", label: "Allergic Reaction", icon: "🌿", color: "#00B894" },
  { id: "spinal_injury", label: "Spinal Injury", icon: "🦴", color: "#636E72" },
  { id: "heart_failure", label: "Heart Failure", icon: "💔", color: "#D63031" },
  { id: "fracture", label: "Fracture", icon: "🦴", color: "#795548" },
  { id: "snake_bite", label: "Snake Bite", icon: "🐍", color: "#4CAF50" },
  { id: "drowning", label: "Drowning", icon: "💧", color: "#0288D1" },
  { id: "electrocution", label: "Electrocution", icon: "⚡", color: "#FFC107" },
  { id: "liver_failure", label: "Liver Failure", icon: "🫀", color: "#8D6E63" },
];

const SEVERITY_LEVELS = [
  { value: 1, label: "Low", color: "#17B86B", bg: "#E8FDF4" },
  { value: 2, label: "Moderate", color: "#FFB21A", bg: "#FFF8E8" },
  { value: 3, label: "High", color: "#FF6B35", bg: "#FFF3EE" },
  { value: 4, label: "Critical", color: "#EE3B3B", bg: "#FFF0F0" },
];

const AMBULANCE_EQUIPMENT_LABELS = {
  oxygen: "Oxygen",
  ventilator: "Ventilator",
  defibrillator: "Defibrillator",
  ecg: "ECG Monitor",
};

const ALL_AMBULANCE_EQUIPMENT = Object.keys(AMBULANCE_EQUIPMENT_LABELS);

const SEVERITY_PAYLOAD_LABELS = {
  1: "low",
  2: "moderate",
  3: "high",
  4: "critical",
};

const VITAL_FIELDS = [
  { key: "oxygen", label: "SpO2 %", placeholder: "92", min: 0, max: 100 },
  { key: "pulse", label: "Pulse", placeholder: "110", min: 0, max: 260 },
  { key: "systolic", label: "Systolic BP", placeholder: "90", min: 0, max: 300 },
  { key: "diastolic", label: "Diastolic BP", placeholder: "60", min: 0, max: 220 },
];

const ACTIVE_CASE_STATUSES = new Set([
  "dispatched",
  "accepted",
  "en_route",
  "on_scene",
  "transporting",
  "arrived",
  "stabilized",
  "en_route_secondary",
]);

function formatCaseLabel(caseRecord) {
  if (!caseRecord) return "";
  return `${(caseRecord.custom_condition || caseRecord.condition || "case").replace(/_/g, " ")} · Case #${caseRecord.id}`;
}

function toNumberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function normalizeVitals(vitalsInput) {
  return Object.fromEntries(
    Object.entries(vitalsInput)
      .map(([key, value]) => [key, toNumberOrNull(value)])
      .filter(([, value]) => value !== null)
  );
}

export function extractVitalsFromText(text) {
  const source = String(text || "").toLowerCase();
  const vitals = {};
  const oxygenMatch =
    source.match(/\b(?:spo2|sp02|oxygen|o2)\s*(?:is|at|:)?\s*(\d{2,3})\b/) ||
    source.match(/\b(\d{2,3})\s*(?:percent|%)\s*(?:spo2|sp02|oxygen|o2)\b/);
  const pulseMatch =
    source.match(/\b(?:pulse|heart rate|hr)\s*(?:is|at|:)?\s*(\d{1,3})\b/) ||
    source.match(/\b(\d{1,3})\s*(?:pulse|heart rate|bpm)\b/);
  const bpMatch =
    source.match(/\b(?:bp|blood pressure)\s*(?:is|at|:)?\s*(\d{2,3})\s*(?:\/|over)\s*(\d{2,3})\b/) ||
    source.match(/\bsystolic\s*(?:is|at|:)?\s*(\d{2,3})\b/);
  const diastolicMatch = source.match(/\bdiastolic\s*(?:is|at|:)?\s*(\d{2,3})\b/);

  if (oxygenMatch) vitals.oxygen = oxygenMatch[1];
  if (pulseMatch) vitals.pulse = pulseMatch[1];
  if (bpMatch) {
    vitals.systolic = bpMatch[1];
    if (bpMatch[2]) {
      vitals.diastolic = bpMatch[2];
    }
  }
  if (diastolicMatch) vitals.diastolic = diastolicMatch[1];

  return vitals;
}

export function buildDispatchPayload({
  selectedCondition,
  aiResult,
  checkedEquipment,
  ambulanceEquipment,
  vitals,
  selectedSeverity,
  lat,
  lng,
  notes,
}) {
  const requiredEquipment = [...new Set(checkedEquipment)];
  return {
    condition: selectedCondition,
    custom_condition: aiResult?.condition_label || null,
    equipment_needed: requiredEquipment,
    required_equipment: requiredEquipment,
    critical_equipment: aiResult?.critical_equipment || [],
    important_equipment: aiResult?.important_equipment || [],
    optional_equipment: aiResult?.optional_equipment || [],
    ambulance_equipment: ambulanceEquipment,
    vitals: normalizeVitals(vitals),
    ambulance_lat: lat,
    ambulance_lng: lng,
    severity: SEVERITY_PAYLOAD_LABELS[selectedSeverity] || "moderate",
    notes: notes && !isInternalNote(notes) ? notes : null,
  };
}

function isInternalNote(text) {
  if (!text) return false;
  const normalized = text.toLowerCase();
  return normalized.includes("rule-based assessment") || normalized.includes("ai offline") || normalized.includes("(ai offline)");
}

async function analyzeWithAI(voiceText) {
  try {
    const res = await api.post("/api/ai/equipment-recommend", { voice_text: voiceText });
    return res.data;
  } catch {
    return null;
  }
}

async function parseVoiceTranscript(transcript) {
  try {
    const res = await api.post("/api/voice/parse", { transcript });
    return res.data;
  } catch {
    return null;
  }
}

export default function Dispatch() {
  const navigate = useNavigate();
  const [selectedCondition, setSelectedCondition] = useState(null);
  const [checkedEquipment, setCheckedEquipment] = useState([]);
  const [ambulanceEquipment, setAmbulanceEquipment] = useState(["oxygen"]);
  const [selectedSeverity, setSelectedSeverity] = useState(2);
  const [vitals, setVitals] = useState({ oxygen: "", pulse: "", systolic: "", diastolic: "" });
  const [notes, setNotes] = useState("");
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [gpsReady, setGpsReady] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [aiSuggestedItems, setAiSuggestedItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [activeCase, setActiveCase] = useState(null);
  const [activeCaseLoaded, setActiveCaseLoaded] = useState(false);
  const [commsPanel, setCommsPanel] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) {
      setLat(30.3165);
      setLng(78.0322);
      setGpsReady(true);
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
        setGpsReady(true);
      },
      () => {
        setLat(30.3165);
        setLng(78.0322);
        setGpsReady(true);
      },
      { enableHighAccuracy: true }
    );
  }, []);

  useEffect(() => {
    if (selectedCondition) {
      setCheckedEquipment(CONDITION_EQUIPMENT[selectedCondition] || []);
      setAiSuggestedItems([]);
    }
  }, [selectedCondition]);

  const fetchActiveCase = useCallback(async () => {
    try {
      const res = await api.get("/api/cases/");
      const items = Array.isArray(res.data) ? res.data : [];
      const latestActiveCase = items
        .filter((item) => ACTIVE_CASE_STATUSES.has(item.status))
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0] || null;
      setActiveCase(latestActiveCase);
    } catch {
      // Leave the comms card hidden if case history cannot be fetched.
    } finally {
      setActiveCaseLoaded(true);
    }
  }, []);

  useEffect(() => {
    fetchActiveCase();
    const interval = setInterval(fetchActiveCase, 15000);
    return () => clearInterval(interval);
  }, [fetchActiveCase]);

  const {
    socketStatus: activeCaseSocketStatus,
    lastEvent: activeCaseSocketEvent,
    sendEvent: sendActiveCaseEvent,
  } = useCaseSocket(activeCase?.id, Boolean(activeCase && commsPanel));

  const applyVoiceAnalysis = useCallback(({ result, parsedVoice, extractedVitals, isRealResult }) => {
    const analysisResult = result || {};
    setError("");
    setAiResult(analysisResult);

    const parsedSeverity = Number(parsedVoice?.severity);
    const fallbackSeverity = Number(analysisResult.severity);
    if (Number.isInteger(parsedSeverity) && parsedSeverity >= 1 && parsedSeverity <= 4) {
      setSelectedSeverity(parsedSeverity);
    } else if (Number.isInteger(fallbackSeverity) && fallbackSeverity >= 1 && fallbackSeverity <= 4) {
      setSelectedSeverity(fallbackSeverity);
    }

    if (analysisResult.notes && isRealResult) {
      setNotes(analysisResult.notes);
    }

    if (analysisResult.matched_condition_id && analysisResult.matched_condition_id !== "other") {
      setSelectedCondition(analysisResult.matched_condition_id);
    }

    if (analysisResult.recommended_equipment?.length) {
      const baseEquip = analysisResult.matched_condition_id !== "other"
        ? CONDITION_EQUIPMENT[analysisResult.matched_condition_id] || []
        : [];
      const normalizeMap = {
        defibrillator: "defibrillator",
        ventilator: "ventilator",
        "ecg monitor": "ecg",
        ecg: "ecg",
        "ct scan": "ct_scan",
        "ct scan access": "ct_scan",
        "blood bank": "blood_bank",
        "blood bags": "blood_bank",
        "icu equipment": "icu_equipment",
        oxygen: "ventilator",
        "oxygen cylinder": "ventilator",
      };
      const normalized = analysisResult.recommended_equipment
        .map((item) => normalizeMap[item.toLowerCase()] || null)
        .filter((item) => item && ALL_EQUIPMENT.includes(item));
      const aiExtra = normalized.filter((item) => !baseEquip.includes(item));
      const merged = [...new Set([...baseEquip, ...normalized])];
      setCheckedEquipment(merged);
      setAiSuggestedItems(aiExtra);
    }

    const parsedVitals = {};
    if (parsedVoice?.spo2 !== null && parsedVoice?.spo2 !== undefined) parsedVitals.oxygen = String(parsedVoice.spo2);
    if (parsedVoice?.pulse !== null && parsedVoice?.pulse !== undefined) parsedVitals.pulse = String(parsedVoice.pulse);
    if (parsedVoice?.bp_systolic !== null && parsedVoice?.bp_systolic !== undefined) parsedVitals.systolic = String(parsedVoice.bp_systolic);
    if (parsedVoice?.bp_diastolic !== null && parsedVoice?.bp_diastolic !== undefined) parsedVitals.diastolic = String(parsedVoice.bp_diastolic);

    const mergedVitals = {
      ...extractedVitals,
      ...parsedVitals,
    };

    if (Object.keys(mergedVitals).length) {
      setVitals((prev) => ({ ...prev, ...mergedVitals }));
    }
  }, []);

  const toggleEquipment = (item) => {
    setCheckedEquipment((prev) => (prev.includes(item) ? prev.filter((entry) => entry !== item) : [...prev, item]));
  };

  const toggleAmbulanceEquipment = (item) => {
    setAmbulanceEquipment((prev) => (prev.includes(item) ? prev.filter((entry) => entry !== item) : [...prev, item]));
  };

  const updateVital = (key, value) => {
    setVitals((prev) => ({ ...prev, [key]: value }));
  };

  const handleSubmit = async () => {
    if (!selectedCondition) {
      setError("Please select a patient condition.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await api.post(
        "/api/dispatch/",
        buildDispatchPayload({
          selectedCondition,
          aiResult,
          checkedEquipment,
          ambulanceEquipment,
          vitals,
          selectedSeverity,
          lat,
          lng,
          notes,
        })
      );
      setActiveCase({
        id: res.data.case_id,
        status: res.data.status || "dispatched",
        condition: selectedCondition,
        custom_condition: aiResult?.condition_label || null,
      });
      navigate("/result", { state: { result: res.data, ambLat: lat, ambLng: lng } });
    } catch (e) {
      setError(e.response?.data?.detail || "Dispatch failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F7FC] font-['Inter',sans-serif] pb-10">
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
        <Suspense fallback={<RouteFallback label="Loading voice controls..." />}>
          <VoiceInput
            analyzeVoiceText={analyzeWithAI}
            parseVoiceText={parseVoiceTranscript}
            extractVitalsFromText={extractVitalsFromText}
            onApplyAnalysis={applyVoiceAnalysis}
            isInternalNote={isInternalNote}
            equipmentLabels={EQUIPMENT_LABELS}
            canRestoreMicMode={Boolean(activeCase)}
            voiceContextReady={activeCaseLoaded}
          />
        </Suspense>

        {activeCase && (
          <div className="bg-white rounded-2xl border border-[#E2E6F0] shadow-sm p-5 mb-6">
            <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
              <div>
                <p className="text-[15px] font-bold text-[#1A1E2E]">Active Case Comms</p>
                <p className="text-[12px] text-[#737A8F]">{formatCaseLabel(activeCase)}</p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[11px] uppercase tracking-wide text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-3 py-1">
                  Socket {activeCaseSocketStatus}
                </span>
                <button
                  onClick={() => setCommsPanel((prev) => (prev === "chat" ? null : "chat"))}
                  className="rounded-xl border border-[#D0D5E8] px-4 py-2 text-[13px] font-semibold text-[#1A1E2E]"
                >
                  Chat
                </button>
                <button
                  onClick={() => setCommsPanel((prev) => (prev === "call" ? null : "call"))}
                  className="rounded-xl bg-[#1A78F2] px-4 py-2 text-[13px] font-semibold text-white"
                >
                  Call
                </button>
              </div>
            </div>

            {commsPanel === "chat" && (
              <Suspense fallback={<RouteFallback label="Loading case chat..." />}>
                <CaseChat
                  caseId={activeCase.id}
                  caseLabel={formatCaseLabel(activeCase)}
                  socketEvent={activeCaseSocketEvent}
                />
              </Suspense>
            )}

            {commsPanel === "call" && (
              <Suspense fallback={<RouteFallback label="Loading call controls..." />}>
                <CallPanel
                  caseId={activeCase.id}
                  caseLabel={formatCaseLabel(activeCase)}
                  socketEvent={activeCaseSocketEvent}
                  sendEvent={sendActiveCaseEvent}
                  socketStatus={activeCaseSocketStatus}
                />
              </Suspense>
            )}
          </div>
        )}

        <div className="flex items-center gap-3 mb-5">
          <div className="flex-1 h-px bg-[#E2E6F0]" />
          <span className="text-[12px] text-[#9EA6BC] font-medium">OR SELECT CONDITION MANUALLY</span>
          <div className="flex-1 h-px bg-[#E2E6F0]" />
        </div>

        <div className="glass-card rounded-xl p-5 mb-6">
          <h3 className="text-[13px] font-semibold text-[#404454] uppercase tracking-wider mb-4">Patient Condition</h3>
          <div className="grid grid-cols-5 gap-3">
            {CONDITIONS.map((condition) => (
              <button
                key={condition.id}
                onClick={() => setSelectedCondition((prev) => (prev === condition.id ? null : condition.id))}
                className="py-3 px-2 rounded-[10px] border-[1.5px] cursor-pointer transition-all text-center"
                style={{
                  borderColor: selectedCondition === condition.id ? condition.color : "#E2E6F0",
                  background: selectedCondition === condition.id ? `${condition.color}15` : "#FAFBFF",
                }}
              >
                <div className="text-[22px] mb-1.5">{condition.icon}</div>
                <div
                  className="text-[11px] leading-tight"
                  style={{
                    fontWeight: selectedCondition === condition.id ? 600 : 400,
                    color: selectedCondition === condition.id ? condition.color : "#4A5068",
                  }}
                >
                  {condition.label}
                </div>
              </button>
            ))}
          </div>
        </div>

        {(selectedCondition || aiResult) && (
          <div className="glass-card rounded-xl p-5 mb-6">
            <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
              <div>
                <h3 className="text-[13px] font-semibold text-[#404454] uppercase tracking-wider">Clinical Signals</h3>
                <p className="text-[12px] text-[#737A8F] mt-1">Sent to the stabilize-first dispatch engine.</p>
              </div>
              <span className="text-[12px] text-[#737A8F] bg-[#F7F7FC] border border-[#E2E6F0] rounded-md px-[10px] py-1">
                {SEVERITY_LEVELS.find((level) => level.value === selectedSeverity)?.label || "Moderate"}
              </span>
            </div>

            <div className="grid grid-cols-4 gap-2 mb-4">
              {SEVERITY_LEVELS.map((level) => {
                const isSelected = selectedSeverity === level.value;
                return (
                  <button
                    key={level.value}
                    onClick={() => setSelectedSeverity(level.value)}
                    className="py-2 px-3 rounded-lg border-[1.5px] text-[12px] font-semibold cursor-pointer transition-all"
                    style={{
                      borderColor: isSelected ? level.color : "#E2E6F0",
                      background: isSelected ? level.bg : "#FAFBFF",
                      color: isSelected ? level.color : "#4A5068",
                    }}
                  >
                    {level.label}
                  </button>
                );
              })}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              {VITAL_FIELDS.map((field) => (
                <label key={field.key} className="block">
                  <span className="text-[12px] text-[#737A8F] block mb-1">{field.label}</span>
                  <input
                    type="number"
                    min={field.min}
                    max={field.max}
                    value={vitals[field.key]}
                    onChange={(e) => updateVital(field.key, e.target.value)}
                    placeholder={field.placeholder}
                    className="w-full px-3 py-2 border border-[#E2E6F0] rounded-lg text-[13px] outline-none text-[#1A1E2E] bg-white"
                  />
                </label>
              ))}
            </div>

            <div>
              <div className="text-[12px] text-[#737A8F] mb-2">Ambulance equipment available now</div>
              <div className="flex flex-wrap gap-2">
                {ALL_AMBULANCE_EQUIPMENT.map((item) => {
                  const isChecked = ambulanceEquipment.includes(item);
                  return (
                    <button
                      key={item}
                      onClick={() => toggleAmbulanceEquipment(item)}
                      className="flex items-center gap-2 px-[12px] py-2 rounded-lg border-[1.5px] cursor-pointer transition-all text-[13px]"
                      style={{
                        borderColor: isChecked ? "#17B86B" : "#E2E6F0",
                        background: isChecked ? "#E8FDF4" : "#FAFBFF",
                        color: isChecked ? "#148A52" : "#4A5068",
                        fontWeight: isChecked ? 500 : 400,
                      }}
                    >
                      <span
                        className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border-[1.5px]"
                        style={{
                          borderColor: isChecked ? "#17B86B" : "#C5CBDC",
                          background: isChecked ? "#17B86B" : "transparent",
                        }}
                      >
                        {isChecked && <span className="text-white text-[10px]">✓</span>}
                      </span>
                      {AMBULANCE_EQUIPMENT_LABELS[item]}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        )}

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
                      : `Auto-suggested for ${CONDITIONS.find((condition) => condition.id === selectedCondition)?.label || "condition"}`}
                  </div>
                </div>
              </div>
              <span className="text-[12px] text-[#737A8F] bg-[#F7F7FC] border border-[#E2E6F0] rounded-md px-[10px] py-1">
                {checkedEquipment.length} selected
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {ALL_EQUIPMENT.map((item) => {
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
                    <span
                      className="w-4 h-4 rounded flex items-center justify-center flex-shrink-0 border-[1.5px] transition-all"
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

        <div className="bg-white border border-[#F0F2F7] rounded-xl p-5 mb-6">
          <label className="text-[12px] text-[#737A8F] block mb-2">Additional Notes (optional)</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
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
            ? (
              <>
                <span className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full" />
                Scanning 188 hospitals...
              </>
            )
            : "🚑  Dispatch Emergency — Find Best Hospital"}
        </button>
        <p className="text-center text-[12px] text-[#9EA6BC] mt-2.5">
          ML engine will score all 188 hospitals across Uttarakhand in real-time
        </p>
      </div>
    </div>
  );
}
