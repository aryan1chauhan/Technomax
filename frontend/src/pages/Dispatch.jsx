// frontend/src/pages/Dispatch.jsx
import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";

// ─── Equipment rules (rule-based fallback + base for AI merge) ────────────────
const CONDITION_EQUIPMENT = {
  cardiac_arrest:   ["defibrillator", "ventilator", "ecg", "blood_bank", "icu_equipment"],
  chest_pain:       ["ecg", "ventilator", "blood_bank"],
  stroke:           ["ct_scan", "ventilator", "blood_bank", "icu_equipment"],
  trauma:           ["blood_bank", "ventilator", "icu_equipment", "ct_scan"],
  respiratory:      ["ventilator", "icu_equipment"],
  burns:            ["ventilator", "blood_bank", "icu_equipment"],
  poisoning:        ["ventilator", "icu_equipment"],
  obstetric:        ["blood_bank", "ventilator", "icu_equipment"],
  pediatric:        ["ventilator", "icu_equipment"],
  diabetic:         ["blood_bank", "icu_equipment"],
  fracture:         ["ct_scan"],
  snake_bite:       ["blood_bank", "ventilator"],
  drowning:         ["ventilator", "icu_equipment", "defibrillator"],
  electrocution:    ["defibrillator", "ventilator", "ecg"],
  seizure:          ["ventilator", "ct_scan", "icu_equipment"],
  allergic_reaction:["ventilator"],
  heart_failure:    ["defibrillator", "ecg", "ventilator", "icu_equipment", "blood_bank"],
  kidney_failure:   ["ventilator", "blood_bank", "icu_equipment"],
  liver_failure:    ["blood_bank", "ventilator", "icu_equipment"],
  spinal_injury:    ["ct_scan", "ventilator", "icu_equipment"],
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
  { id: "cardiac_arrest", label: "Cardiac Arrest",   icon: "♥",  color: "#EE3B3B" },
  { id: "chest_pain",     label: "Chest Pain",       icon: "⚡", color: "#FF6B35" },
  { id: "stroke",         label: "Stroke / TIA",     icon: "🧠", color: "#9B59B6" },
  { id: "trauma",         label: "Trauma / Injury",  icon: "🩹", color: "#E67E22" },
  { id: "respiratory",    label: "Respiratory",       icon: "💨", color: "#3498DB" },
  { id: "burns",          label: "Burns",             icon: "🔥", color: "#E74C3C" },
  { id: "poisoning",      label: "Poisoning / OD",   icon: "☠",  color: "#2ECC71" },
  { id: "obstetric",      label: "Obstetric",         icon: "🤰", color: "#E91E8C" },
  { id: "pediatric",      label: "Pediatric",         icon: "👶", color: "#00BCD4" },
  { id: "diabetic",       label: "Diabetic Emergency",icon: "💉", color: "#FF9800" },
];

const SEVERITY_LEVELS = [
  { value: 1, label: "Low",      color: "#17B86B", bg: "#E8FDF4" },
  { value: 2, label: "Moderate", color: "#FFB21A", bg: "#FFF8E8" },
  { value: 3, label: "High",     color: "#FF6B35", bg: "#FFF3EE" },
  { value: 4, label: "Critical", color: "#EE3B3B", bg: "#FFF0F0" },
];

// ─── AI Equipment Analyzer (via backend proxy) ──────────────────────────────
async function analyzeWithAI(voiceText) {
  try {
    const res = await api.post("/api/ai/equipment-recommend", { voice_text: voiceText });
    return res.data;
  } catch {
    return null;
  }
}

// ─── Voice Pulse Animation ────────────────────────────────────────────────────
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

// ─── Main Component ───────────────────────────────────────────────────────────
export default function Dispatch() {
  const navigate = useNavigate();

  // Form state
  const [selectedCondition, setSelectedCondition] = useState(null);
  const [checkedEquipment, setCheckedEquipment] = useState([]);
  const [notes, setNotes] = useState("");
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [gpsLabel, setGpsLabel] = useState("Acquiring GPS...");
  const [gpsReady, setGpsReady] = useState(false);

  // Voice state
  const [isListening, setIsListening] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [showVoicePanel, setShowVoicePanel] = useState(false);
  const [aiSuggestedItems, setAiSuggestedItems] = useState([]);

  // Misc
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const recognitionRef = useRef(null);

  // ── Get GPS on mount
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

  // ── Auto-select equipment when condition changes
  useEffect(() => {
    if (selectedCondition) {
      const base = CONDITION_EQUIPMENT[selectedCondition] || [];
      setCheckedEquipment(base);
      setAiSuggestedItems([]);
    }
  }, [selectedCondition]);

  // ── Voice recognition
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
  }, []);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  // ── Analyze voice with backend AI
  const analyzeVoice = useCallback(async () => {
    if (!voiceTranscript.trim()) return;
    setIsAnalyzing(true);
    setError("");
    const result = await analyzeWithAI(voiceTranscript);
    if (result) {
      setAiResult(result);
      if (result.notes) setNotes(result.notes);
      if (result.matched_condition_id && result.matched_condition_id !== "other") {
        setSelectedCondition(result.matched_condition_id);
      }
      // Merge AI equipment suggestions with condition defaults
      if (result.recommended_equipment?.length) {
        const baseEquip = result.matched_condition_id !== "other"
          ? (CONDITION_EQUIPMENT[result.matched_condition_id] || [])
          : [];
        // Normalize AI suggestions to match our equipment keys
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
      setNotes(voiceTranscript);
      setError("AI analysis unavailable — transcript saved as notes. Select condition manually.");
    }
    setIsAnalyzing(false);
  }, [voiceTranscript]);

  const toggleEquipment = (item) => {
    setCheckedEquipment(prev =>
      prev.includes(item) ? prev.filter(e => e !== item) : [...prev, item]
    );
  };

  // ── Submit dispatch
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
        notes: notes || null,
      });
      navigate("/result", { state: { result: res.data, lat, lng } });
    } catch (e) {
      setError(e.response?.data?.detail || "Dispatch failed. Please try again.");
    } finally { setLoading(false); }
  };

  const currentSeverityObj = aiResult ? SEVERITY_LEVELS.find(s => s.value === aiResult.severity) : null;

  return (
    <div className="min-h-screen bg-[#F7F7FC] font-['Inter',sans-serif]">

      {/* Nav */}
      <nav className="bg-white border-b border-[#F0F2F7] h-16 flex items-center px-8">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative w-9 h-9 bg-[#EE3B3B] rounded-lg flex items-center justify-center">
            <div className="absolute w-4 h-1.5 bg-white rounded-sm" />
            <div className="absolute w-1.5 h-4 bg-white rounded-sm" />
          </div>
          <div>
            <p className="text-[16px] font-bold text-[#1A1E2E] leading-none">MediRoute</p>
            <p className="text-[11px] text-[#737A8F]">Dispatch Console</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-[12px] font-medium ${gpsReady ? "bg-[#E8FDF2] text-[#17B86B]" : "bg-[#FFF8E0] text-[#FFB21A]"}`}>
          <span className={`w-2 h-2 rounded-full ${gpsReady ? "bg-[#17B86B]" : "bg-[#FFB21A]"}`} />
          {gpsReady ? "GPS Active" : "GPS Acquiring..."}
        </div>
      </nav>

      <div className="max-w-[960px] mx-auto px-8 py-8">

        {/* ── VOICE INPUT SECTION ─────────────────────────────────────── */}
        <div className={`rounded-xl border-[1.5px] p-5 mb-6 transition-all ${showVoicePanel ? "bg-[#EBF3FF] border-[#1A78F2]" : "bg-white border-[#F0F2F7]"}`}>
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
                    <span className="font-semibold text-[#17B86B] text-[14px]">AI Analysis Complete</span>
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
                  {aiResult.notes && (
                    <div className="bg-[#FFFBEB] border border-[#FFE082] rounded-lg px-3 py-2 text-[13px] text-[#7A5C00]">
                      <strong>Hospital note:</strong> {aiResult.notes}
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

        {/* ── CONDITION GRID ──────────────────────────────────────────── */}
        <div className="bg-white border border-[#F0F2F7] rounded-xl p-5 mb-6">
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

        {/* ── EQUIPMENT PANEL ─────────────────────────────────────────── */}
        {(selectedCondition || aiResult) && (
          <div className="bg-white border-[1.5px] border-[#1A78F2] rounded-xl p-5 mb-6 animate-[fadeIn_0.3s_ease]">
            <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}`}</style>
            <div className="flex items-center justify-between flex-wrap gap-2 mb-4">
              <div className="flex items-center gap-2">
                <span className="text-[14px]">🧰</span>
                <div>
                  <div className="font-semibold text-[14px] text-[#1A1E2E]">Recommended Equipment</div>
                  <div className="text-[12px] text-[#737A8F]">
                    {aiSuggestedItems.length > 0
                      ? `Rule-based + ${aiSuggestedItems.length} AI suggestions`
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

        {/* ── NOTES ───────────────────────────────────────────────────── */}
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

        {/* ── ERROR ───────────────────────────────────────────────────── */}
        {error && (
          <div className="bg-[#FFF0F0] border border-[#FFCDD2] rounded-lg px-4 py-3 text-[#EE3B3B] text-[13px] mb-4 flex items-center gap-2">
            ⚠ {error}
          </div>
        )}

        {/* ── DISPATCH BUTTON ─────────────────────────────────────────── */}
        <button
          onClick={handleSubmit}
          disabled={loading || !gpsReady}
          className="w-full h-[60px] bg-[#EE3B3B] hover:bg-[#D02F2F] disabled:opacity-60 text-white font-bold text-[16px] rounded-xl transition flex items-center justify-center gap-3"
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
