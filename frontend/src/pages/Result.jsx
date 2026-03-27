import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

export default function Result() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const [revealed, setRevealed] = useState(0);
  const [blink, setBlink] = useState(true);

  const result = state?.result;
  const ambLat = state?.lat;
  const ambLng = state?.lng;

  useEffect(() => {
    if (!result) { navigate("/dispatch"); return; }
    // Reveal lines one by one for dramatic effect
    const t = setInterval(() => setRevealed((r) => r + 1), 180);
    return () => clearInterval(t);
  }, [result, navigate]);

  useEffect(() => {
    const t = setInterval(() => setBlink((b) => !b), 500);
    return () => clearInterval(t);
  }, []);

  if (!result) return null;

  const score = result.final_score ?? result.score ?? 0;
  const scoreBar = Math.round(score * 20); // out of 20 chars
  const scoreBarStr = "█".repeat(scoreBar) + "░".repeat(20 - scoreBar);
  const scoreColor = score > 0.7 ? "#00ff41" : score > 0.4 ? "#ffff00" : "#ff4444";

  const lines = [
    { label: "DISPATCH COMPLETE", value: "", type: "header" },
    { label: "", value: "", type: "blank" },
    { label: "ASSIGNED HOSPITAL", value: result.hospital_name?.toUpperCase() || "—", type: "main" },
    { label: "ADDRESS", value: result.address || "—", type: "sub" },
    { label: "", value: "", type: "blank" },
    { label: "ML SCORE", value: `${(score * 100).toFixed(1)}%  [${scoreBarStr}]`, type: "score" },
    { label: "DISTANCE", value: `${result.distance_km?.toFixed(2) || "—"} km`, type: "stat" },
    { label: "ETA", value: `${result.eta_minutes || "—"} minutes`, type: "stat" },
    { label: "AVAILABLE BEDS", value: `${result.beds ?? "—"}`, type: "stat" },
    { label: "ICU BEDS", value: `${result.icu ?? "—"}`, type: "stat" },
    { label: "CASE ID", value: `#${result.case_id || result.id || "—"}`, type: "sub" },
    { label: "", value: "", type: "blank" },
    { label: "ROUTING STATUS", value: "READY — press MAP to begin navigation", type: "action" },
  ];

  const getStyle = (type) => {
    if (type === "header") return { color: "#00ff41", fontSize: 16, fontWeight: "bold", letterSpacing: 3 };
    if (type === "main") return { color: "#00ff41", fontSize: 15, fontWeight: "bold" };
    if (type === "score") return { color: scoreColor, fontSize: 13 };
    if (type === "stat") return { color: "#00cc33", fontSize: 13 };
    if (type === "action") return { color: "#ffff00", fontSize: 12 };
    if (type === "sub") return { color: "#00882a", fontSize: 12 };
    return { color: "#00882a", fontSize: 12 };
  };

  return (
    <div style={styles.root}>
      <div style={styles.scanlines} />
      <div style={styles.container}>

        <div style={styles.topBar}>
          ╔══════════════════════════════════════════════════════╗
        </div>
        <div style={styles.topMid}>
          ║&nbsp;&nbsp;🚨 DISPATCH RESULT — OPTIMAL HOSPITAL SELECTED
          &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║
        </div>
        <div style={styles.topBot}>
          ╠══════════════════════════════════════════════════════╣
        </div>

        <div style={styles.resultBox}>
          {lines.slice(0, revealed).map((line, i) => (
            <div key={i} style={{ marginBottom: 6 }}>
              {line.type === "blank" ? (
                <div style={{ height: 6 }} />
              ) : line.type === "header" ? (
                <div style={getStyle(line.type)}>▶ {line.label}</div>
              ) : (
                <div style={{ display: "flex", gap: 12 }}>
                  <span style={{ color: "#006600", fontSize: 12, minWidth: 160 }}>
                    {line.label}
                  </span>
                  <span style={getStyle(line.type)}>
                    {line.value}
                  </span>
                </div>
              )}
            </div>
          ))}
          {revealed < lines.length && (
            <span style={{ color: "#00ff41" }}>{blink ? "█" : " "}</span>
          )}
        </div>

        <div style={styles.topBot}>
          ╚══════════════════════════════════════════════════════╝
        </div>

        {/* Actions */}
        {revealed >= lines.length && (
          <div style={styles.actions}>
            <button
              style={styles.btnPrimary}
              onClick={() =>
                navigate("/map", {
                  state: {
                    hospital: {
                      lat: result.hospital_lat,
                      lng: result.hospital_lng,
                      name: result.hospital_name,
                    },
                    caseId: result.case_id || result.id,
                    ambLat,
                    ambLng,
                  },
                })
              }
            >
              [ 🗺 OPEN NAVIGATION MAP ]
            </button>
            <button
              style={styles.btnSecondary}
              onClick={() => navigate("/dispatch")}
            >
              [ ← NEW DISPATCH ]
            </button>
          </div>
        )}

        {/* Why this hospital */}
        {revealed >= lines.length && result.reason && (
          <div style={styles.reason}>
            <div style={{ color: "#006600", fontSize: 11, marginBottom: 4 }}>
              ┌─── ML REASONING ───┐
            </div>
            <div style={{ color: "#00882a", fontSize: 11 }}>{result.reason}</div>
          </div>
        )}

        <div style={styles.footer}>
          MediRoute ML Engine • RandomForest • 15 features • 188 hospitals evaluated
        </div>
      </div>
    </div>
  );
}

const BG = "#0a0a0a"; const MONO = "'Courier New', monospace";

const styles = {
  root: { minHeight: "100vh", background: BG, fontFamily: MONO, padding: "1.5rem", position: "relative" },
  scanlines: { position: "fixed", inset: 0, background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.015) 2px,rgba(0,255,65,0.015) 4px)", pointerEvents: "none", zIndex: 1 },
  container: { maxWidth: 760, margin: "0 auto", zIndex: 2, position: "relative" },
  topBar: { color: "#00882a", fontSize: 13 },
  topMid: { color: "#00ff41", fontSize: 13, fontWeight: "bold" },
  topBot: { color: "#00882a", fontSize: 13, marginBottom: 8 },
  resultBox: { padding: "1rem 1.5rem", minHeight: 240 },
  actions: { display: "flex", gap: 12, marginTop: "1.5rem", flexWrap: "wrap" },
  btnPrimary: { flex: 1, background: "transparent", border: "2px solid #00ff41", color: "#00ff41", fontFamily: MONO, fontSize: 13, padding: "12px", cursor: "pointer", letterSpacing: 2, fontWeight: "bold" },
  btnSecondary: { background: "transparent", border: "1px solid #006600", color: "#006600", fontFamily: MONO, fontSize: 12, padding: "12px 16px", cursor: "pointer" },
  reason: { marginTop: "1rem", padding: "0.5rem 1rem", border: "1px solid #003300" },
  footer: { color: "#1a3a1a", fontSize: 10, textAlign: "center", marginTop: "2rem", letterSpacing: 1 },
};
