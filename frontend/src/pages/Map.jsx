import { useState, useEffect, useRef } from "react";
import { useLocation, useNavigate, Navigate } from "react-router-dom";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

// Fix leaflet default icon paths broken by Vite
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

// Custom ambulance icon — red pulsing dot
const ambulanceIcon = L.divIcon({
  className: "",
  html: `<div style="
    width:18px;height:18px;border-radius:50%;
    background:#ef4444;border:2px solid #fff;
    box-shadow:0 0 0 0 rgba(239,68,68,0.7);
    animation:amb-pulse 1.2s infinite;
  "></div>
  <style>
    @keyframes amb-pulse {
      0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.7); }
      70%  { box-shadow: 0 0 0 10px rgba(239,68,68,0); }
      100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
    }
  </style>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

// Custom hospital icon — green cross
const hospitalIcon = L.divIcon({
  className: "",
  html: `<div style="
    width:28px;height:28px;border-radius:6px;
    background:#10b981;border:2px solid #fff;
    display:flex;align-items:center;justify-content:center;
    font-size:16px;line-height:1;color:#fff;font-weight:bold;
    box-shadow:0 2px 8px rgba(16,185,129,0.5);
  ">+</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

const fetchRoute = async (start, end) => {
  const key = import.meta.env.VITE_ORS_API_KEY;
  if (!key) return null;
  const url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${key}&start=${start[1]},${start[0]}&end=${end[1]},${end[0]}`;
  try {
    const res = await fetch(url);
    const json = await res.json();
    if (json.features?.[0]) {
      // ORS returns [lng,lat] — Leaflet wants [lat,lng]
      return json.features[0].geometry.coordinates.map(([lng, lat]) => [lat, lng]);
    }
    return null;
  } catch (err) {
    console.error("Route fetch failed:", err);
    return null;
  }
};

// Subcomponent: animates ambulance marker along route
function AmbulanceAnimator({ routeCoords, etaMinutes, onEtaUpdate, wsRef, caseId }) {
  const markerRef = useRef(null);
  const map = useMap();
  const indexRef = useRef(0);

  useEffect(() => {
    if (!routeCoords || routeCoords.length === 0) return;
    const total = routeCoords.length;

    const move = () => {
      const i = indexRef.current;
      if (i >= total) { onEtaUpdate(0); return; }
      const pos = routeCoords[i];
      if (markerRef.current) markerRef.current.setLatLng(pos);
      map.panTo(pos, { animate: true, duration: 0.8 });

      const remaining = total - i;
      const newEta = Math.max(1, Math.round((remaining / total) * etaMinutes));
      onEtaUpdate(newEta);

      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          case_id: caseId,
          lat: pos[0],
          lng: pos[1],
          eta_minutes: newEta,
          timestamp: Date.now(),
        }));
      }
      indexRef.current++;
      setTimeout(move, 1000);
    };

    setTimeout(move, 2500);
  }, [routeCoords]);

  if (!routeCoords || routeCoords.length === 0) return null;
  return <Marker position={routeCoords[0]} icon={ambulanceIcon} ref={markerRef} />;
}

export default function MapPage() {
  // FIX #2: ALL hooks declared before any early return
  const location = useLocation();
  const navigate = useNavigate();
  const wsRef = useRef(null);

  const data = location.state;

  // FIX #3: Read ambLat/ambLng (set by Dispatch.jsx) with fallbacks
  const ambLat = data?.ambLat ?? data?.ambulance_lat ?? 30.3165;
  const ambLng = data?.ambLng ?? data?.ambulance_lng ?? 78.0322;
  const hospLat = data?.result?.hospital_lat ?? data?.lat ?? 30.33;
  const hospLng = data?.result?.hospital_lng ?? data?.lng ?? 78.05;

  const startLatLng = [ambLat, ambLng];
  const endLatLng = [hospLat, hospLng];
  const centerLatLng = [
    (ambLat + hospLat) / 2,
    (ambLng + hospLng) / 2,
  ];

  const [routeCoords, setRouteCoords] = useState(null);
  const [eta, setEta] = useState(data?.result?.eta_minutes ?? 0);
  const [distance] = useState(data?.result?.distance_km ?? "--");
  const [simulationLogs, setSimulationLogs] = useState([]);
  const [routeLoading, setRouteLoading] = useState(true);

  // WebSocket connection
  useEffect(() => {
    if (!data?.result?.case_id) return;
    let reconnectTimer;
    const connect = () => {
      const ws = new WebSocket(`ws://${window.location.host}/ws/ambulance/${data.result.case_id}`);
      ws.onopen = () => console.log("WS connected");
      ws.onerror = (e) => console.error("WS error", e);
      ws.onclose = () => { reconnectTimer = setTimeout(connect, 2000); };
      wsRef.current = ws;
    };
    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }
    };
  }, [data?.result?.case_id]);

  // Fetch route
  useEffect(() => {
    if (!data) return;
    fetchRoute(startLatLng, endLatLng).then((coords) => {
      setRouteCoords(coords);
      setRouteLoading(false);
    });
  }, []);

  // Simulated network logs
  useEffect(() => {
    const cases = ["Head Injury", "Cardiac Arrest", "Major Trauma", "Resp. Failure", "Severe Burn"];
    const locs = ["Sector 7, Main Rd", "Highway 42", "Downtown Square", "Industrial Park B"];
    const interval = setInterval(() => {
      const msg = `[SYS] Triage Event: ${cases[Math.floor(Math.random() * cases.length)]} at ${locs[Math.floor(Math.random() * locs.length)]}. Assigning unit...`;
      setSimulationLogs((prev) => [msg, ...prev].slice(0, 5));
    }, 8000);
    return () => clearInterval(interval);
  }, []);

  // FIX #2: Early return AFTER all hooks
  if (!data) return <Navigate to="/dispatch" replace />;

  const caseId = data.result?.case_id;
  const hospitalName = data.result?.hospital_name ?? "Destination";
  const etaMinutes = data.result?.eta_minutes ?? 0;

  return (
    <div style={{ height: "100vh", width: "100vw", background: "#0a0a0a", display: "flex", flexDirection: "column", fontFamily: "system-ui, sans-serif" }}>

      {/* Top bar */}
      <div style={{ padding: "12px 20px", background: "rgba(15,23,42,0.97)", borderBottom: "1px solid rgba(255,255,255,0.06)", display: "flex", justifyContent: "space-between", alignItems: "center", zIndex: 1000, flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
          <button onClick={() => navigate(-1)} style={{ background: "transparent", border: "1px solid rgba(255,255,255,0.12)", borderRadius: "6px", color: "#fff", cursor: "pointer", padding: "4px 12px", fontSize: "0.9rem" }}>← Back</button>
          <span style={{ color: "#fff", fontWeight: 700, fontSize: "1.1rem", letterSpacing: "0.05em" }}>LIVE TRACKING</span>
          <span style={{ padding: "3px 8px", background: "rgba(239,68,68,0.15)", color: "#ef4444", borderRadius: "4px", fontSize: "0.7rem", fontWeight: "bold", border: "1px solid rgba(239,68,68,0.3)", letterSpacing: "1px" }}>● ACTIVE</span>
        </div>
        <div style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
          CASE: <span style={{ color: "#fff" }}>#{caseId || "---"}</span>
        </div>
      </div>

      {/* Map */}
      <div style={{ flex: 1, position: "relative" }}>
        <MapContainer
          center={centerLatLng}
          zoom={13}
          style={{ width: "100%", height: "100%" }}
          zoomControl={true}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          />

          {/* Hospital marker */}
          <Marker position={endLatLng} icon={hospitalIcon}>
            <Popup>{hospitalName}</Popup>
          </Marker>

          {/* Route line */}
          {routeCoords && (
            <>
              <Polyline positions={routeCoords} color="#ef4444" weight={5} opacity={0.25} />
              <Polyline positions={routeCoords} color="#ef4444" weight={2.5} opacity={0.9} />
            </>
          )}

          {/* Fallback static ambulance if no route */}
          {!routeCoords && !routeLoading && (
            <Marker position={startLatLng} icon={ambulanceIcon}>
              <Popup>Ambulance</Popup>
            </Marker>
          )}

          {/* Animated ambulance along route */}
          {routeCoords && (
            <AmbulanceAnimator
              routeCoords={routeCoords}
              etaMinutes={etaMinutes}
              onEtaUpdate={setEta}
              wsRef={wsRef}
              caseId={caseId}
            />
          )}
        </MapContainer>

        {/* Info panel — top right */}
        <div style={{ position: "absolute", top: 16, right: 16, background: "rgba(15,23,42,0.88)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "14px", padding: "18px", color: "#fff", width: "230px", zIndex: 999 }}>
          <div style={{ color: "#94a3b8", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "1px", fontWeight: 600, marginBottom: 6 }}>Target Hospital</div>
          <div style={{ fontSize: "1rem", fontWeight: "bold", marginBottom: 14, lineHeight: 1.3 }}>{hospitalName}</div>

          <div style={{ color: "#94a3b8", fontSize: "0.7rem", textTransform: "uppercase", letterSpacing: "1px", fontWeight: 600, marginBottom: 4 }}>Estimated Arrival</div>
          <div style={{ fontSize: "2.8rem", fontWeight: 800, color: eta === 0 ? "#10b981" : "#3b82f6", lineHeight: 1 }}>
            {eta === 0 ? "ARRIVED" : eta}
            {eta !== 0 && <span style={{ fontSize: "0.9rem", color: "#94a3b8", marginLeft: 5 }}>min</span>}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginTop: 14, paddingTop: 14, borderTop: "1px solid rgba(255,255,255,0.07)" }}>
            <div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8", fontWeight: 600 }}>SPEED</div>
              <div style={{ fontWeight: "bold", color: "#f8fafc", fontSize: "0.85rem" }}>{eta === 0 ? "0" : "40"} km/h</div>
            </div>
            <div>
              <div style={{ fontSize: "0.65rem", color: "#94a3b8", fontWeight: 600 }}>DISTANCE</div>
              <div style={{ fontWeight: "bold", color: "#f8fafc", fontSize: "0.85rem" }}>{distance} km</div>
            </div>
          </div>

          {routeLoading && (
            <div style={{ marginTop: 12, fontSize: "0.7rem", color: "#94a3b8" }}>Fetching route...</div>
          )}
        </div>

        {/* Network logs — bottom left */}
        <div style={{ position: "absolute", bottom: 20, left: 20, background: "rgba(15,23,42,0.88)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "14px", padding: "14px", color: "#fff", width: "360px", zIndex: 999, fontFamily: "ui-monospace, monospace" }}>
          <div style={{ color: "#10b981", fontSize: "0.75rem", fontWeight: "bold", borderBottom: "1px solid rgba(16,185,129,0.2)", paddingBottom: 8, marginBottom: 10, display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ display: "inline-block", width: 6, height: 6, background: "#10b981", borderRadius: "50%" }}></span>
            ACTIVE NETWORK LOGS
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: "0.75rem" }}>
            {simulationLogs.length === 0
              ? <span style={{ color: "#64748b", fontStyle: "italic" }}>Monitoring incoming dispatch streams...</span>
              : simulationLogs.map((log, i) => (
                <div key={i} style={{ color: i === 0 ? "#f8fafc" : "#64748b", opacity: 1 - i * 0.15, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: i === 0 ? 500 : 400 }}>{log}</div>
              ))
            }
          </div>
        </div>
      </div>
    </div>
  );
}
