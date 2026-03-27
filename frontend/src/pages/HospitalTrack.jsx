import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import api from "../api/axios";

// Fix leaflet default icon paths broken by Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const ambulanceIcon = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;border-radius:50%;background:#ef4444;border:2px solid #fff;box-shadow:0 0 0 0 rgba(239,68,68,0.7);animation:amb-pulse 1.2s infinite;"></div>
  <style>@keyframes amb-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.7)}70%{box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}}</style>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const hospitalIcon = L.divIcon({
  className: "",
  html: `<div style="width:28px;height:28px;border-radius:6px;background:#10b981;border:2px solid #fff;display:flex;align-items:center;justify-content:center;font-size:16px;color:#fff;font-weight:bold;box-shadow:0 2px 8px rgba(16,185,129,0.5);">+</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

export default function HospitalTrack() {
  const { case_id } = useParams();
  const navigate = useNavigate();
  const wsRef = useRef(null);

  const [caseData, setCaseData] = useState(null);
  const [ambulancePos, setAmbulancePos] = useState(null);
  const [eta, setEta] = useState(null);
  const [arrived, setArrived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isReady, setIsReady] = useState(false);

  // Fetch case data on mount
  useEffect(() => {
    const fetchCase = async () => {
      try {
        // /api/cases/hospital returns cases assigned to this hospital
        const res = await api.get("/api/cases/hospital");
        const cases = Array.isArray(res.data) ? res.data : (res.data.items || []);
        const found = cases.find((c) => String(c.id) === String(case_id));
        if (!found) {
          setError("Case not found or not assigned to your hospital.");
          setLoading(false);
          return;
        }
        setCaseData(found);
        setEta(found.eta_minutes);

        // FIX #8: Use hospital lat/lng from case data instead of hardcoded position
        // The backend returns hospital_lat/hospital_lng in dispatch response
        // which is stored on the case record
      } catch (err) {
        setError("Failed to load case data.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchCase();
  }, [case_id]);

  // WebSocket for live ambulance GPS
  useEffect(() => {
    if (!case_id) return;
    let reconnectTimer;
    const connect = () => {
      const ws = new WebSocket(`ws://${window.location.host}/ws/hospital/${case_id}`);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.lat && msg.lng) setAmbulancePos([msg.lat, msg.lng]);
          if (msg.eta_minutes !== undefined) {
            setEta(msg.eta_minutes);
            if (msg.eta_minutes === 0) setArrived(true);
          }
        } catch { /* ignore malformed messages */ }
      };
      ws.onerror = (e) => console.error("WS error", e);
      ws.onclose = () => { reconnectTimer = setTimeout(connect, 2000); };
      wsRef.current = ws;
    };
    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    };
  }, [case_id]);

  const handleMarkReady = async () => {
    if (!caseData?.assigned_hospital_id) return;
    try {
      // Toggle hospital accepting status to signal readiness
      await api.put(`/api/hospitals/${caseData.assigned_hospital_id}/availability`, {
        accepting: true,
        status_message: `Ready for case #${case_id}`,
      });
      setIsReady(true);
    } catch (err) {
      console.error("Failed to mark ready:", err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    navigate("/login");
  };

  if (loading) {
    return (
      <div style={styles.root}>
        <div style={styles.scanlines} />
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh", color: GREEN, fontFamily: MONO, fontSize: 14 }}>
          [ LOADING CASE DATA... ]
        </div>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div style={styles.root}>
        <div style={styles.scanlines} />
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100vh", gap: 16, color: RED, fontFamily: MONO }}>
          <div style={{ fontSize: 14 }}>⚠ {error || "Case not found"}</div>
          <button onClick={() => navigate("/hospital/dashboard")} style={styles.btn}>← BACK TO DASHBOARD</button>
        </div>
      </div>
    );
  }

  // FIX #8: Get hospital position from case data (hospital_lat/hospital_lng)
  // Fallback chain: case data fields → Dehradun centre if completely missing
  const hospLat = caseData.hospital_lat ?? caseData.assigned_hospital_lat ?? 30.3165;
  const hospLng = caseData.hospital_lng ?? caseData.assigned_hospital_lng ?? 78.0322;
  const hospPos = [hospLat, hospLng];

  // Ambulance: use live WS position, else fall back to case's recorded ambulance coords
  const ambPos = ambulancePos ?? (
    caseData.ambulance_lat && caseData.ambulance_lng
      ? [caseData.ambulance_lat, caseData.ambulance_lng]
      : null
  );

  const mapCenter = ambPos
    ? [(ambPos[0] + hospLat) / 2, (ambPos[1] + hospLng) / 2]
    : hospPos;

  const scorePercent = Math.round((caseData.final_score || 0) * 100);
  const scoreColor = scorePercent > 70 ? GREEN : scorePercent > 40 ? YELLOW : RED;
  const scoreBar = "█".repeat(Math.round(scorePercent / 5)) + "░".repeat(20 - Math.round(scorePercent / 5));

  return (
    <div style={styles.root}>
      <div style={styles.scanlines} />
      <div style={styles.container}>

        {/* Header */}
        <div style={styles.header}>
          <div style={{ color: DIM, fontSize: 13 }}>╔══════════════════════════════════════════════════════╗</div>
          <div style={{ color: arrived ? GREEN : YELLOW, fontSize: 14, fontWeight: "bold" }}>
            ║&nbsp;&nbsp;🏥 HOSPITAL TRACKING CONSOLE &nbsp;•&nbsp;
            <span style={{ color: arrived ? GREEN : RED }}>
              {arrived ? "● ARRIVED" : "● INCOMING"}
            </span>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║
          </div>
          <div style={{ color: DIM, fontSize: 13 }}>╚══════════════════════════════════════════════════════╝</div>
        </div>

        {/* Case info panel */}
        <div style={styles.infoPanel}>
          <div style={styles.infoPanelHeader}>┌─── CASE #{caseData.id} ────────────────────────────────┐</div>
          <div style={styles.infoGrid}>
            <div style={styles.infoItem}>
              <span style={styles.infoLabel}>CONDITION</span>
              <span style={{ ...styles.infoValue, color: RED, fontWeight: "bold" }}>{caseData.condition?.toUpperCase()}</span>
            </div>
            <div style={styles.infoItem}>
              <span style={styles.infoLabel}>ETA</span>
              <span style={{ ...styles.infoValue, color: arrived ? GREEN : YELLOW, fontSize: 18 }}>
                {arrived ? "ARRIVED" : `${eta ?? "--"} MIN`}
              </span>
            </div>
            <div style={styles.infoItem}>
              <span style={styles.infoLabel}>DISTANCE</span>
              <span style={styles.infoValue}>{caseData.distance_km ?? "--"} KM</span>
            </div>
            <div style={styles.infoItem}>
              <span style={styles.infoLabel}>ML SCORE</span>
              <span style={{ ...styles.infoValue, color: scoreColor }}>{scorePercent}%</span>
            </div>
          </div>
          <div style={{ padding: "0 1rem 0.5rem", color: DIM, fontSize: 11 }}>
            SCORE &gt; <span style={{ color: scoreColor, fontFamily: MONO }}>{scoreBar}</span> {scorePercent}%
          </div>
          {caseData.equipment_needed?.length > 0 && (
            <div style={{ padding: "0 1rem 0.5rem", color: DIM, fontSize: 11 }}>
              EQUIPMENT &gt; <span style={{ color: GREEN }}>{caseData.equipment_needed.join(" | ").toUpperCase()}</span>
            </div>
          )}
          <div style={styles.infoPanelFooter}>└────────────────────────────────────────────────────┘</div>
        </div>

        {/* Map */}
        <div style={styles.mapWrap}>
          <MapContainer center={mapCenter} zoom={13} style={{ width: "100%", height: "100%" }} zoomControl={true}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
            />
            {/* FIX #8: Hospital marker at correct dynamic position */}
            <Marker position={hospPos} icon={hospitalIcon}>
              <Popup>{caseData.hospital_name || "Your Hospital"}</Popup>
            </Marker>
            {ambPos && (
              <>
                <Marker position={ambPos} icon={ambulanceIcon}>
                  <Popup>Ambulance — ETA {eta} min</Popup>
                </Marker>
                <Polyline positions={[ambPos, hospPos]} color="#ef4444" weight={2} dashArray="6,6" opacity={0.7} />
              </>
            )}
            {!ambPos && (
              <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%,-50%)", color: YELLOW, fontFamily: MONO, fontSize: 12, background: "rgba(0,0,0,0.7)", padding: "8px 12px", borderRadius: 4, zIndex: 1000, pointerEvents: "none" }}>
                Waiting for ambulance GPS...
              </div>
            )}
          </MapContainer>
        </div>

        {/* Action buttons */}
        <div style={styles.actions}>
          <button
            onClick={handleMarkReady}
            disabled={isReady}
            style={isReady ? styles.btnDone : styles.btnGreen}
          >
            {isReady ? "[ ✓ MARKED READY ]" : "[ MARK HOSPITAL READY ]"}
          </button>
          <button
            onClick={() => { window.location.href = `tel:112`; }}
            style={styles.btnRed}
          >
            [ 📞 CALL AMBULANCE — 112 ]
          </button>
          <button onClick={() => navigate("/hospital/dashboard")} style={styles.btn}>
            [ ← DASHBOARD ]
          </button>
          <button onClick={handleLogout} style={styles.btnLogout}>
            [ LOGOUT ]
          </button>
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
  container: { maxWidth: 900, margin: "0 auto", zIndex: 2, position: "relative" },
  header: { marginBottom: "1rem" },
  infoPanel: { marginBottom: "1rem" },
  infoPanelHeader: { color: DIM, fontSize: 12, marginBottom: 8 },
  infoPanelFooter: { color: DIM, fontSize: 12, marginTop: 4 },
  infoGrid: { display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, padding: "0.5rem 1rem" },
  infoItem: { display: "flex", flexDirection: "column", gap: 3 },
  infoLabel: { color: DIM, fontSize: 10, letterSpacing: 1 },
  infoValue: { color: GREEN, fontSize: 14, fontWeight: "bold" },
  mapWrap: { height: 360, borderRadius: 4, overflow: "hidden", border: `1px solid ${DIM}`, marginBottom: "1rem" },
  actions: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 },
  btn: { background: "transparent", border: `1px solid ${DIM}`, color: DIM, fontFamily: MONO, fontSize: 12, padding: "10px", cursor: "pointer", letterSpacing: 1 },
  btnGreen: { background: "#001a00", border: `1px solid ${GREEN}`, color: GREEN, fontFamily: MONO, fontSize: 12, padding: "10px", cursor: "pointer", letterSpacing: 1, fontWeight: "bold" },
  btnDone: { background: "#001a00", border: `1px solid ${DIM}`, color: DIM, fontFamily: MONO, fontSize: 12, padding: "10px", cursor: "not-allowed", letterSpacing: 1 },
  btnRed: { background: "#1a0000", border: `1px solid ${RED}`, color: RED, fontFamily: MONO, fontSize: 12, padding: "10px", cursor: "pointer", letterSpacing: 1, fontWeight: "bold" },
  btnLogout: { background: "transparent", border: `1px solid #333`, color: "#333", fontFamily: MONO, fontSize: 11, padding: "10px", cursor: "pointer", letterSpacing: 1 },
};
