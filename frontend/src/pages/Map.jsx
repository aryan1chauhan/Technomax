import { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, Polyline } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix leaflet default icon broken by Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl:       "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl:     "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const ambulanceIcon = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;border-radius:50%;background:#ef4444;border:3px solid #fff;box-shadow:0 0 0 0 rgba(239,68,68,0.7);animation:amb-pulse 1.2s infinite;"></div>
  <style>@keyframes amb-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.7)}70%{box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}}</style>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const hospitalIcon = L.divIcon({
  className: "",
  html: `<div style="width:32px;height:32px;border-radius:8px;background:#10b981;border:3px solid #fff;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:bold;color:#fff;box-shadow:0 4px 12px rgba(16,185,129,0.5);">+</div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
});

const fetchRoute = async (start, end) => {
  const key = import.meta.env.VITE_ORS_API_KEY;
  if (!key) return null;
  // ORS expects [lng, lat]
  const url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${key}&start=${start[1]},${start[0]}&end=${end[1]},${end[0]}`;
  try {
    const res = await fetch(url);
    const json = await res.json();
    if (json.features?.[0]) {
      // ORS returns [lng,lat] coords — Leaflet needs [lat,lng]
      return json.features[0].geometry.coordinates.map(([lng, lat]) => [lat, lng]);
    }
    return null;
  } catch (err) {
    console.error("Route fetch failed:", err);
    return null;
  }
};

// Moves a marker along route coords at 1 point/second
function useAmbulanceAnimation({ routeCoords, etaMinutes, onEtaUpdate, wsRef, caseId, markerRef }) {
  useEffect(() => {
    if (!routeCoords || routeCoords.length === 0) return;
    const total = routeCoords.length;
    let index = 0;

    const move = () => {
      if (index >= total) { onEtaUpdate(0); return; }
      const pos = routeCoords[index];
      if (markerRef.current) markerRef.current.setLatLng(pos);
      const newEta = Math.max(1, Math.round(((total - index) / total) * etaMinutes));
      onEtaUpdate(newEta);
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ case_id: caseId, lat: pos[0], lng: pos[1], eta_minutes: newEta, timestamp: Date.now() }));
      }
      index++;
      setTimeout(move, 1000);
    };
    const timer = setTimeout(move, 2500);
    return () => clearTimeout(timer);
  }, [routeCoords]);
}

export default function MapPage() {
  // ALL hooks before any early return (Rules of Hooks)
  const location = useLocation();
  const navigate  = useNavigate();
  const wsRef     = useRef(null);
  const markerRef = useRef(null);

  const data = location.state;

  // FIX: Parse state shape produced by Result.jsx:
  // { ambLat, ambLng, result: { hospital_lat, hospital_lng, hospital_name, case_id, eta_minutes, distance_km } }
  const ambLat   = data?.ambLat   ?? data?.ambulance_lat ?? 30.3165;
  const ambLng   = data?.ambLng   ?? data?.ambulance_lng ?? 78.0322;
  const hospLat  = data?.result?.hospital_lat  ?? data?.hospital?.lat  ?? 30.33;
  const hospLng  = data?.result?.hospital_lng  ?? data?.hospital?.lng  ?? 78.05;
  const hospName = data?.result?.hospital_name ?? data?.hospital?.name ?? "Destination";
  const caseId   = data?.result?.case_id       ?? data?.caseId;
  const etaMins  = data?.result?.eta_minutes   ?? 0;
  const distKm   = data?.result?.distance_km   ?? "--";

  const startLatLng  = [ambLat, ambLng];
  const endLatLng    = [hospLat, hospLng];
  const centerLatLng = [(ambLat + hospLat) / 2, (ambLng + hospLng) / 2];

  const [routeCoords, setRouteCoords]       = useState(null);
  const [eta, setEta]                       = useState(etaMins);
  const [routeLoading, setRouteLoading]     = useState(true);
  const [simulationLogs, setSimulationLogs] = useState([]);

  // WebSocket
  useEffect(() => {
    if (!caseId) return;
    let reconnectTimer;
    const connect = () => {
      const ws = new WebSocket(`ws://${window.location.host}/ws/ambulance/${caseId}`);
      ws.onopen  = () => console.log("WS connected");
      ws.onerror = (e) => console.error("WS error", e);
      ws.onclose = () => { reconnectTimer = setTimeout(connect, 2000); };
      wsRef.current = ws;
    };
    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    };
  }, [caseId]);

  // Fetch route
  useEffect(() => {
    if (!data) return;
    fetchRoute(startLatLng, endLatLng).then(coords => {
      setRouteCoords(coords);
      setRouteLoading(false);
    });
  }, []);

  // Simulated network logs
  useEffect(() => {
    const cases = ["Head Injury", "Cardiac Arrest", "Major Trauma", "Resp. Failure", "Severe Burn"];
    const locs  = ["Sector 7, Main Rd", "Highway 58", "Clock Tower, Dehradun", "BHEL Haridwar"];
    const id = setInterval(() => {
      setSimulationLogs(prev => [
        `[SYS] Triage: ${cases[Math.floor(Math.random()*cases.length)]} at ${locs[Math.floor(Math.random()*locs.length)]}. Assigning unit...`,
        ...prev,
      ].slice(0, 5));
    }, 8000);
    return () => clearInterval(id);
  }, []);

  // Ambulance animation hook — uses markerRef internally
  useAmbulanceAnimation({ routeCoords, etaMinutes: etaMins, onEtaUpdate: setEta, wsRef, caseId, markerRef });

  // Early return AFTER all hooks
  if (!data) return <Navigate to="/dispatch" replace />;

  return (
    <div style={{ height: "100vh", width: "100vw", background: "#0f172a", display: "flex", flexDirection: "column", fontFamily: "system-ui, sans-serif" }}>

      {/* Top bar */}
      <div style={{ padding: "12px 20px", background: "rgba(15,23,42,0.97)", borderBottom: "1px solid rgba(255,255,255,0.07)", display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 1000, flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button onClick={() => navigate(-1)} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.15)", borderRadius: 6, color: "#fff", cursor: "pointer", padding: "4px 14px", fontSize: "0.9rem" }}>← Back</button>
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "1.05rem", letterSpacing: "0.05em" }}>LIVE TRACKING</span>
          <span style={{ padding: "3px 10px", background: "rgba(239,68,68,0.15)", color: "#ef4444", borderRadius: 4, fontSize: "0.7rem", fontWeight: "bold", border: "1px solid rgba(239,68,68,0.3)", letterSpacing: 1 }}>● ACTIVE</span>
        </div>
        <div style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
          CASE: <span style={{ color: "#fff" }}>#{caseId || "---"}</span>
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1, position: "relative" }}>
        <MapContainer
          center={centerLatLng}
          zoom={12}
          style={{ width: "100%", height: "100%" }}
          zoomControl
        >
          {/* FIX: Use CartoDB dark tiles — no token needed, no black screen */}
          <TileLayer
            attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {/* Hospital marker */}
          <Marker position={endLatLng} icon={hospitalIcon}>
            <Popup><strong>{hospName}</strong></Popup>
          </Marker>

          {/* Route line */}
          {routeCoords && (
            <>
              <Polyline positions={routeCoords} color="#ef4444" weight={6} opacity={0.2} />
              <Polyline positions={routeCoords} color="#ef4444" weight={3} opacity={0.9} />
            </>
          )}

          {/* Static ambulance marker if no route yet */}
          {!routeCoords && !routeLoading && (
            <Marker position={startLatLng} icon={ambulanceIcon}>
              <Popup>Ambulance start position</Popup>
            </Marker>
          )}

          {/* Animated ambulance — rendered after route loads */}
          {routeCoords && (
            <Marker position={routeCoords[0]} icon={ambulanceIcon} ref={markerRef}>
              <Popup>Ambulance</Popup>
            </Marker>
          )}
        </MapContainer>

        {/* Info panel */}
        <div style={{ position: "absolute", top: 16, right: 16, background: "rgba(15,23,42,0.92)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 14, padding: "18px 20px", color: "#fff", width: 230, zIndex: 999 }}>
          <div style={{ color: "#94a3b8", fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: 1, fontWeight: 600, marginBottom: 5 }}>Target Hospital</div>
          <div style={{ fontSize: "0.95rem", fontWeight: "bold", marginBottom: 14, lineHeight: 1.3 }}>{hospName}</div>

          <div style={{ color: "#94a3b8", fontSize: "0.68rem", textTransform: "uppercase", letterSpacing: 1, fontWeight: 600, marginBottom: 4 }}>ETA</div>
          <div style={{ fontSize: "2.6rem", fontWeight: 800, color: eta === 0 ? "#10b981" : "#3b82f6", lineHeight: 1 }}>
            {eta === 0 ? "ARRIVED" : eta}
            {eta !== 0 && <span style={{ fontSize: "0.85rem", color: "#94a3b8", marginLeft: 5 }}>min</span>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 14, paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.08)" }}>
            <div>
              <div style={{ fontSize: "0.62rem", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>Speed</div>
              <div style={{ fontWeight: "bold", color: "#f1f5f9", fontSize: "0.85rem" }}>{eta === 0 ? "0" : "40"} km/h</div>
            </div>
            <div>
              <div style={{ fontSize: "0.62rem", color: "#94a3b8", fontWeight: 600, textTransform: "uppercase" }}>Distance</div>
              <div style={{ fontWeight: "bold", color: "#f1f5f9", fontSize: "0.85rem" }}>{distKm} km</div>
            </div>
          </div>

          {routeLoading && (
            <div style={{ marginTop: 10, fontSize: "0.7rem", color: "#94a3b8" }}>Calculating route...</div>
          )}
        </div>

        {/* Network logs */}
        <div style={{ position: "absolute", bottom: 20, left: 20, background: "rgba(15,23,42,0.92)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: "14px 16px", color: "#fff", width: 360, zIndex: 999, fontFamily: "ui-monospace, monospace" }}>
          <div style={{ color: "#10b981", fontSize: "0.72rem", fontWeight: "bold", borderBottom: "1px solid rgba(16,185,129,0.2)", paddingBottom: 8, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 6, height: 6, background: "#10b981", borderRadius: "50%", display: "inline-block" }} />
            ACTIVE NETWORK LOGS
          </div>
          {simulationLogs.length === 0
            ? <div style={{ color: "#475569", fontStyle: "italic", fontSize: "0.72rem" }}>Monitoring dispatch streams...</div>
            : simulationLogs.map((log, i) => (
              <div key={i} style={{ fontSize: "0.72rem", color: i === 0 ? "#f1f5f9" : "#475569", opacity: 1 - i * 0.15, marginBottom: 5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{log}</div>
            ))
          }
        </div>
      </div>
    </div>
  );
}
