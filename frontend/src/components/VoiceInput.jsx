import React, { useCallback, useEffect, useRef, useState } from "react";

const MIC_MODE_STORAGE_KEY = "dispatch_voice_mode";
const CONFIRMATION_THRESHOLD = 0.6;
const FLASH_DURATION_MS = 2200;

function VoicePulse({ active }) {
  return (
    <div className="flex items-center gap-[3px] h-6">
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          className="w-[3px] rounded-sm transition-all duration-150"
          style={{
            background: active ? "#1A78F2" : "#D0D5E8",
            height: active ? `${[10, 18, 24, 16, 8][i]}px` : "6px",
            animation: active ? `pulse_${i} 0.8s ease-in-out ${i * 0.1}s infinite alternate` : "none",
          }}
        />
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

export default function VoiceInput({
  analyzeVoiceText,
  parseVoiceText,
  extractVitalsFromText,
  onApplyAnalysis,
  isInternalNote,
  equipmentLabels,
  canRestoreMicMode = false,
  voiceContextReady = false,
}) {
  const recognitionRef = useRef(null);
  const restartWantedRef = useRef(false);
  const lastProcessedTranscriptRef = useRef("");
  const feedbackTimeoutRef = useRef(null);
  const [isListening, setIsListening] = useState(false);
  const [micModeEnabled, setMicModeEnabled] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [aiResult, setAiResult] = useState(null);
  const [showVoicePanel, setShowVoicePanel] = useState(false);
  const [aiIsRealResult, setAiIsRealResult] = useState(false);
  const [parseFeedback, setParseFeedback] = useState([]);

  const clearFeedbackTimer = useCallback(() => {
    if (feedbackTimeoutRef.current) {
      clearTimeout(feedbackTimeoutRef.current);
      feedbackTimeoutRef.current = null;
    }
  }, []);

  const stopListening = useCallback(() => {
    restartWantedRef.current = false;
    const recognition = recognitionRef.current;
    recognitionRef.current = null;
    try {
      recognition?.stop();
    } catch {
      // Some browsers throw when stop() is called during teardown.
    }
    setIsListening(false);
  }, []);

  const pushParseFeedback = useCallback((parsedVoice) => {
    const feedback = [];
    const entries = [
      { key: "spo2", label: "SpO2" },
      { key: "pulse", label: "Pulse" },
      { key: "bp_systolic", label: "BP Systolic" },
      { key: "bp_diastolic", label: "BP Diastolic" },
      { key: "severity", label: "Severity" },
    ];

    for (const entry of entries) {
      const value = parsedVoice?.[entry.key];
      if (value === null || value === undefined) continue;
      const confidence = Number(parsedVoice?.confidence?.[entry.key] ?? 0);
      feedback.push({
        key: entry.key,
        label: entry.label,
        value,
        confidence,
        confirmed: confidence >= CONFIRMATION_THRESHOLD,
      });
    }

    setParseFeedback(feedback);
    clearFeedbackTimer();
    if (feedback.length > 0) {
      feedbackTimeoutRef.current = setTimeout(() => {
        setParseFeedback([]);
      }, FLASH_DURATION_MS);
    }

    return feedback.length > 0;
  }, [clearFeedbackTimer]);

  const processTranscript = useCallback(async (rawTranscript) => {
    const transcript = String(rawTranscript || "").replace(/\s+/g, " ").trim();
    if (!transcript || transcript === lastProcessedTranscriptRef.current) {
      return;
    }

    lastProcessedTranscriptRef.current = transcript;
    setIsAnalyzing(true);
    setVoiceError("");

    const [analysisResult, parsedVoice] = await Promise.all([
      analyzeVoiceText(transcript),
      parseVoiceText ? parseVoiceText(transcript) : Promise.resolve(null),
    ]);

    const isLowConfidenceCase = Boolean(analysisResult?.low_confidence);
    const validAnalysis = analysisResult && !isLowConfidenceCase ? analysisResult : null;
    const parsedViaRegex = extractVitalsFromText(transcript);
    const parsedHasValues = pushParseFeedback(parsedVoice || {});

    if (validAnalysis) {
      setAiResult(validAnalysis);
      setAiIsRealResult(!isInternalNote(validAnalysis.notes || ""));
    } else {
      setAiResult(null);
      setAiIsRealResult(false);
    }

    if (!parsedHasValues && !validAnalysis) {
      setVoiceError("Speech was unintelligible or no vitals were detected. Please repeat clearly.");
    }

    onApplyAnalysis({
      transcript,
      result: validAnalysis || analysisResult || {},
      parsedVoice,
      extractedVitals: parsedViaRegex,
      isRealResult: validAnalysis ? !isInternalNote(validAnalysis.notes || "") : false,
    });

    setIsAnalyzing(false);
  }, [analyzeVoiceText, extractVitalsFromText, isInternalNote, onApplyAnalysis, parseVoiceText, pushParseFeedback]);

  const startListening = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) {
      setVoiceError("Voice input not supported. Use Chrome or Edge.");
      setMicModeEnabled(false);
      return;
    }

    const recognition = new SR();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-IN";
    recognition.onresult = (e) => {
      const combined = Array.from(e.results)
        .map((result) => result[0]?.transcript || "")
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      setVoiceTranscript(combined);

      if (Array.from(e.results).some((result) => result.isFinal) && combined) {
        void processTranscript(combined);
      }
    };
    recognition.onerror = (e) => {
      setVoiceError(
        e.error === "not-allowed"
          ? "Microphone access denied. Please allow mic permissions."
          : `Voice error: ${e.error}`
      );
      if (e.error === "not-allowed") {
        setMicModeEnabled(false);
      }
      restartWantedRef.current = false;
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
      recognitionRef.current = null;

      if (restartWantedRef.current) {
        window.setTimeout(() => {
          if (restartWantedRef.current) {
            startListening();
          }
        }, 250);
      }
    };
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
    setVoiceError("");
    setShowVoicePanel(true);
    setAiResult(null);
    setAiIsRealResult(false);
  }, [processTranscript]);

  const setMicMode = useCallback((enabled) => {
    setMicModeEnabled(enabled);
    try {
      localStorage.setItem(MIC_MODE_STORAGE_KEY, enabled ? "on" : "off");
    } catch {
      // Ignore storage failures in private mode.
    }

    if (enabled) {
      restartWantedRef.current = true;
      setShowVoicePanel(true);
      setVoiceError("");
      if (!isListening) {
        startListening();
      }
    } else {
      stopListening();
    }
  }, [isListening, startListening, stopListening]);

  const toggleMicMode = useCallback(() => {
    setMicMode(!micModeEnabled);
  }, [micModeEnabled, setMicMode]);

  const onMicToggleKeyDown = useCallback((event) => {
    if (event.key === " " || event.key === "Enter") {
      event.preventDefault();
      toggleMicMode();
    }
  }, [toggleMicMode]);

  useEffect(() => {
    if (!voiceContextReady) return;

    if (!canRestoreMicMode) {
      restartWantedRef.current = false;
      setMicModeEnabled(false);
      try {
        localStorage.setItem(MIC_MODE_STORAGE_KEY, "off");
      } catch {
        // Ignore storage failures in private mode.
      }
      return;
    }

    try {
      const savedMicMode = localStorage.getItem(MIC_MODE_STORAGE_KEY) === "on";
      if (savedMicMode) {
        setMicModeEnabled(true);
        setShowVoicePanel(true);
      }
    } catch {
      // Ignore storage failures in private mode.
    }
  }, [canRestoreMicMode, voiceContextReady]);

  useEffect(() => {
    try {
      localStorage.setItem(MIC_MODE_STORAGE_KEY, micModeEnabled ? "on" : "off");
    } catch {
      // Ignore storage failures in private mode.
    }
  }, [micModeEnabled]);

  useEffect(() => {
    if (micModeEnabled && !isListening) {
      restartWantedRef.current = true;
      startListening();
    }
  }, [isListening, micModeEnabled, startListening]);

  useEffect(() => {
    const handleBeforeUnload = () => {
      stopListening();
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      stopListening();
      clearFeedbackTimer();
    };
  }, [clearFeedbackTimer, stopListening]);

  const analyzeVoice = useCallback(async () => {
    if (!voiceTranscript.trim()) return;
    await processTranscript(voiceTranscript);
  }, [processTranscript, voiceTranscript]);

  const currentSeverityObj = aiResult
    ? [
        { value: 1, label: "Low", color: "#17B86B", bg: "#E8FDF4" },
        { value: 2, label: "Moderate", color: "#FFB21A", bg: "#FFF8E8" },
        { value: 3, label: "High", color: "#FF6B35", bg: "#FFF3EE" },
        { value: 4, label: "Critical", color: "#EE3B3B", bg: "#FFF0F0" },
      ].find((s) => s.value === aiResult.severity)
    : null;

  return (
    <div
      className={`glass-card rounded-xl border-[1.5px] p-5 mb-6 transition-all ${
        showVoicePanel ? "bg-white/80 border-[#1A78F2] shadow-[0_4px_20px_rgba(26,120,242,0.15)]" : "border-transparent"
      }`}
    >
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
          aria-label={showVoicePanel ? "Close voice input panel" : "Open voice input panel"}
          onClick={() => {
            if (showVoicePanel && micModeEnabled) {
              setVoiceError("Turn mic mode off before closing voice input.");
              return;
            }
            setShowVoicePanel((v) => !v);
          }}
          className={`px-[18px] py-2 rounded-lg border-[1.5px] text-[13px] font-medium cursor-pointer transition-all ${
            showVoicePanel ? "bg-[#1A78F2] border-[#1A78F2] text-white" : "bg-white border-[#D0D5E8] text-[#1A1E2E] hover:border-[#1A78F2]"
          }`}
        >
          {showVoicePanel ? "Close" : "Open Voice Input"}
        </button>
      </div>

      {showVoicePanel && (
        <div className="mt-5">
          <div className="flex items-center gap-4 mb-4 flex-wrap">
            <button
              aria-label={micModeEnabled ? "Turn microphone mode off" : "Turn microphone mode on"}
              aria-pressed={micModeEnabled}
              onClick={toggleMicMode}
              onKeyDown={onMicToggleKeyDown}
              className="w-[52px] h-[52px] rounded-full border-none text-white text-[20px] cursor-pointer flex items-center justify-center flex-shrink-0 transition-all"
              style={{
                background: micModeEnabled ? "#EE3B3B" : "#1A78F2",
                boxShadow: isListening ? "0 0 0 6px rgba(238,59,59,0.15)" : "none",
              }}
            >
              {micModeEnabled ? "⏹" : "🎙"}
            </button>
            <div className="flex-1">
              <div className="flex items-center gap-3 mb-2" role="status" aria-live="polite">
                <VoicePulse active={isListening} />
                <span className={`text-[12px] ${isListening ? "text-[#1A78F2] font-medium" : "text-[#737A8F]"}`}>
                  {isListening ? "Listening..." : "Not listening"}
                </span>
                <span className="text-[11px] text-[#4A5068] border border-[#D0D5E8] rounded-full px-2 py-0.5">
                  Mic {micModeEnabled ? "On" : "Off"}
                </span>
              </div>
              {voiceTranscript && (
                <div aria-live="polite" className="bg-white border border-[#D0D5E8] rounded-lg px-[14px] py-[10px] text-[14px] text-[#1A1E2E] italic leading-relaxed">
                  "{voiceTranscript}"
                </div>
              )}
              {voiceError && (
                <p role="alert" className="mt-1.5 text-[12px] text-[#EE3B3B] font-medium">
                  ⚠ {voiceError}
                </p>
              )}
            </div>
          </div>

          {voiceTranscript && (
            <button
              aria-label="Analyze latest voice transcript"
              onClick={analyzeVoice}
              disabled={isAnalyzing}
              className="w-full py-[11px] rounded-lg border-none text-white text-[14px] font-semibold flex items-center justify-center gap-2 transition-colors"
              style={{ background: isAnalyzing ? "#8FB8F6" : "#1A78F2", cursor: isAnalyzing ? "not-allowed" : "pointer" }}
            >
              {isAnalyzing ? (
                <>
                  <span className="w-[14px] h-[14px] border-2 border-white/40 border-t-white rounded-full inline-block animate-spin" />
                  AI Analyzing…
                </>
              ) : "✨ Analyze with AI & Get Equipment Recommendations"}
            </button>
          )}

          {parseFeedback.length > 0 && (
            <div className="mt-3 rounded-lg border border-[#DDE3F1] bg-[#F9FBFF] p-3" role="status" aria-live="polite">
              <div className="text-[11px] text-[#4A5068] mb-2">Voice parse updates:</div>
              <div className="flex flex-wrap gap-2">
                {parseFeedback.map((item) => (
                  <span
                    key={item.key}
                    className="text-[11px] rounded-full px-2.5 py-1 font-semibold"
                    style={{
                      background: item.confirmed ? "#E8FDF4" : "#FFF7E5",
                      color: item.confirmed ? "#0F8A52" : "#9A6800",
                      border: `1px solid ${item.confirmed ? "#B9EFD4" : "#F7D48A"}`,
                    }}
                  >
                    {item.label} -&gt; {item.value} {item.confirmed ? "Confirmed" : "Unconfirmed"}
                  </span>
                ))}
              </div>
            </div>
          )}

          {aiResult && (
            <div className="mt-4 bg-white border-[1.5px] border-[#17B86B] rounded-[10px] p-4">
              <div className="flex items-center gap-1.5 mb-3">
                <span className="text-[14px]">✅</span>
                <span className="font-semibold text-[#17B86B] text-[14px]">
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
              {aiResult.notes && !isInternalNote(aiResult.notes) && (
                <div className="bg-[#FFFBEB] border border-[#FFE082] rounded-lg px-3 py-2 text-[13px] text-[#7A5C00]">
                  <strong>Hospital note:</strong> {aiResult.notes}
                </div>
              )}
              {Array.isArray(aiResult.recommended_equipment) && aiResult.recommended_equipment.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[#E8F5E9]">
                  <div className="text-[11px] text-[#737A8F] mb-2">Recommended equipment from voice analysis:</div>
                  <div className="flex flex-wrap gap-1.5">
                    {aiResult.recommended_equipment.map((item) => (
                      <span key={item} className="text-[11px] bg-[#EBF3FF] text-[#1A78F2] border border-[#BDD6FF] rounded px-2 py-0.5 font-medium">
                        ✓ {equipmentLabels[item] || item}
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
  );
}
