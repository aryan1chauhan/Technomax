import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

// FIX #7: All 20 conditions matching backend training data exactly (spaces, not underscores)
// These are sent to backend with replace(/_/g,' ') so display uses underscores for UI
const CONDITIONS = [
  "cardiac_arrest",
  "stroke",
  "trauma",
  "respiratory",
  "burns",
  "fracture",
  "poisoning",
  "obstetric",
  "general",
  "head_injury",
  "internal_bleeding",
  "spinal_injury",
  "seizure",
  "diabetic",
  "chest_pain",
  "eye_injury",
  "allergic_reaction",
  "heat_stroke",
  "infection",
  "kidney_failure",
];

const EQUIPMENT_OPTIONS = [
  "ventilator",
  "defibrillator",
  "ct_scan",
  "blood_bank",
  "icu_equipment",
  "oxygen",
];

export default function Dispatch() {
  const navigate = useNavigate();
  const [condition, setCondition] = useState("");
  const [equipment, setEquipment] = useState([]);
  const [lat, setLat] = useState(null);
  const [lng, setLng] = useState(null);
  const [gpsStatus, setGpsStatus] = useState("ACQUIRING...");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [blink, setBlink] = useState(true);
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setBlink((b) => !b), 500);
    const t2 = setInterval(() => setTime(new Date()), 1000);
    return () => { clearInterval(t); clearInterval(t2); };
  }, []);

  useEffect(() => {
    if (!navigator.geolocation) {
      setGpsStatus("GPS UNAVAILABLE — using default");
      setLat(30.3165); setLng(78.0322);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLat(pos.coords.latitude);
        setLng(pos.coords.longitude);
        setGpsStatus(`LOCKED — ${pos.coords.latitude.toFixed(5)}, ${pos.coords.longitude.toFixed(5)}`);
      },
      () => {
        setGpsStatus("GPS FAILED — using default coords");
        setLat(30.3165); setLng(78.0322);
      },
      { enableHighAccuracy: true }
    );
  }, []);

  const toggleEquipment = (item) => {
    setEquipment((prev) =>
      prev.includes(item) ? prev.filter((e) => e !== item) : [...prev, item]
    );
  };

  const handleDispatch = async () => {
    if (!condition) { setError("ERR: Select patient condition"); return; }
    if (!lat || !lng) { setError("ERR: GPS coordinates unavailable"); return; }
    setLoading(true);
    setError("");
    try {
      const token = localStorage.getItem("token");

      // Convert underscores to spaces to match backend training data format
      const conditionForBackend = condition.replace(/_/g, " ");

      const res = await axios.post(
        "/api/dispatch/",
        {
          condition: conditionForBackend,
          equipment_needed: equipment,
          ambulance_lat: lat,
          ambulance_lng: lng,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      // Pass ambLat/ambLng — Map.jsx reads these exact keys
      navigate("/result", { state: { result: res.data, ambLat: lat, ambLng: lng } });
    } catch (e) {
      setError(`DISPATCH FAILED: ${e.response?.data?.detail || e.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.root}>
      <div style={styles.scanlines} />
      <div style={styles.container}>

        {/* Header */}
        <div style={styles.header}>
          <div style={styles.headerTop}>╔══════════════════════════════════════════════════════╗</div>
          <div style={styles.headerMid}>
            ║&nbsp;&nbsp;🚨 MEDIROUTE DISPATCH CONSOLE &nbsp;•&nbsp;
            <span style={styles.dim}>AMBULANCE UNIT</span>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║
          </div>
          <div style={styles.headerBot}>╚══════════════════════════════════════════════════════╝</div>
          <div style={styles.timestamp}>
            {time.toLocaleTimeString()} IST &nbsp;|&nbsp;
            <span style={{ color: lat ? "#00ff41" : "#ffff00" }}>GPS: {gpsStatus}</span>
          </div>
        </div>

        {/* Condition — now 20 conditions in a 4-col grid */}
        <div style={styles.section}>
          <div style={styles.sectionHead}>┌─── PATIENT CONDITION ──────────────────────────────┐</div>
          <div style={styles.grid4}>
            {CONDITIONS.map((c) => (
              <button
                key={c}
                onClick={() => setCondition(c)}
                style={condition === c ? styles.optionActive : styles.option}
              >
                {condition === c ? "▶ " : "  "}
                {c.replace(/_/g, " ").toUpperCase()}
              </button>
            ))}
          </div>
          <div style={styles.sectionFoot}>└────────────────────────────────────────────────────┘</div>
        </div>

        {/* Equipment */}
        <div style={styles.section}>
          <div style={styles.sectionHead}>┌─── EQUIPMENT REQUIRED (select all that apply) ─────┐</div>
          <div style={styles.grid3}>
            {EQUIPMENT_OPTIONS.map((eq) => (
              <button
                key={eq}
                onClick={() => toggleEquipment(eq)}
                style={equipment.includes(eq) ? styles.eqActive : styles.eqOption}
              >
                [{equipment.includes(eq) ? "✓" : " "}] {eq.replace(/_/g, " ").toUpperCase()}
              </button>
            ))}
          </div>
          <div style={styles.sectionFoot}>└────────────────────────────────────────────────────┘</div>
        </div>

        {/* Status line */}
        <div style={styles.statusLine}>
          STATUS &gt; CONDITION: <span style={styles.green}>{condition ? condition.replace(/_/g, " ").toUpperCase() : "NOT SET"}</span>
          &nbsp;|&nbsp; EQUIPMENT: <span style={styles.green}>{equipment.length ? equipment.join(", ") : "NONE"}</span>
        </div>

        {error && <div style={styles.error}>⚠ {error}</div>}

        <button
          onClick={handleDispatch}
          disabled={loading}
          style={loading ? styles.dispatchBtnLoading : styles.dispatchBtn}
        >
          {loading
            ? `[ SCANNING 188 HOSPITALS${blink ? "..." : "   "} ]`
            : "[ 🚨 INITIATE DISPATCH → FIND BEST HOSPITAL ]"}
        </button>

        <div style={styles.footer}>
          MEDIROUTE • 188 hospitals • Uttarakhand • ML-powered dispatch
        </div>
      </div>
    </div>
  );
}

const GREEN = "#00ff41"; const DIM = "#00aa2a";
const RED = "#ff4444"; const YELLOW = "#ffff00";
const BG = "#0a0a0a"; const MONO = "'Courier New', monospace";

const styles = {
  root: { minHeight: "100vh", background: BG, fontFamily: MONO, padding: "1rem", position: "relative" },
  scanlines: { position: "fixed", inset: 0, background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.015) 2px,rgba(0,255,65,0.015) 4px)", pointerEvents: "none", zIndex: 1 },
  container: { maxWidth: 820, margin: "0 auto", zIndex: 2, position: "relative" },
  header: { marginBottom: "1.5rem" },
  headerTop: { color: DIM, fontSize: 13 },
  headerMid: { color: GREEN, fontSize: 14, fontWeight: "bold" },
  headerBot: { color: DIM, fontSize: 13 },
  timestamp: { color: DIM, fontSize: 11, marginTop: 6, letterSpacing: 1 },
  dim: { color: DIM },
  section: { marginBottom: "1.2rem" },
  sectionHead: { color: DIM, fontSize: 12, marginBottom: 8 },
  sectionFoot: { color: DIM, fontSize: 12, marginTop: 8 },
  // FIX #7: 4-col grid to fit 20 conditions without scrolling
  grid4: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, padding: "0 1rem" },
  grid3: { display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, padding: "0 1rem" },
  option: { background: "transparent", border: `1px solid #1a3a1a`, color: DIM, fontFamily: MONO, fontSize: 10, padding: "7px 4px", cursor: "pointer", textAlign: "left", letterSpacing: 0.5 },
  optionActive: { background: "#001a00", border: `1px solid ${GREEN}`, color: GREEN, fontFamily: MONO, fontSize: 10, padding: "7px 4px", cursor: "pointer", textAlign: "left", letterSpacing: 0.5 },
  eqOption: { background: "transparent", border: `1px solid #1a3a1a`, color: DIM, fontFamily: MONO, fontSize: 11, padding: "8px 4px", cursor: "pointer", textAlign: "left" },
  eqActive: { background: "#001500", border: `1px solid ${GREEN}`, color: GREEN, fontFamily: MONO, fontSize: 11, padding: "8px 4px", cursor: "pointer", textAlign: "left" },
  statusLine: { color: DIM, fontSize: 12, marginBottom: "1rem", letterSpacing: 1 },
  green: { color: GREEN },
  error: { color: RED, fontSize: 13, marginBottom: "1rem" },
  dispatchBtn: { width: "100%", background: "transparent", border: `2px solid ${GREEN}`, color: GREEN, fontFamily: MONO, fontSize: 14, padding: "14px", cursor: "pointer", letterSpacing: 2, fontWeight: "bold" },
  dispatchBtnLoading: { width: "100%", background: "#001500", border: `2px solid ${DIM}`, color: DIM, fontFamily: MONO, fontSize: 14, padding: "14px", cursor: "not-allowed", letterSpacing: 2 },
  footer: { color: "#1a3a1a", fontSize: 11, textAlign: "center", marginTop: "2rem", letterSpacing: 1 },
};
