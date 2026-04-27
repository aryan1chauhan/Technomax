import { useCallback, useEffect, useRef, useState } from "react";
import { MapContainer, Marker, Popup, Polyline, TileLayer } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
});

const LERP_DURATION_MS = 3000;
const TILE_URL = "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const TILE_ATTR = '&copy; <a href="https://carto.com/">CARTO</a>';

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function bearingBetween(lat1, lng1, lat2, lng2) {
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const deltaLambda = ((lng2 - lng1) * Math.PI) / 180;
  const y = Math.sin(deltaLambda) * Math.cos(phi2);
  const x = Math.cos(phi1) * Math.sin(phi2) - Math.sin(phi1) * Math.cos(phi2) * Math.cos(deltaLambda);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

function makeAmbulanceIcon(bearing = 0) {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 40 40">
      <g transform="rotate(${bearing}, 20, 20)">
        <rect x="6" y="10" width="28" height="20" rx="4" fill="#1d4ed8" stroke="#fff" stroke-width="1.5"/>
        <rect x="10" y="14" width="8" height="8" rx="1" fill="#fff"/>
        <rect x="13" y="11" width="2" height="14" rx="1" fill="#ef4444"/>
        <rect x="10" y="17" width="8" height="2" rx="1" fill="#ef4444"/>
        <circle cx="12" cy="30" r="3" fill="#1e293b" stroke="#94a3b8" stroke-width="1"/>
        <circle cx="28" cy="30" r="3" fill="#1e293b" stroke="#94a3b8" stroke-width="1"/>
        <polygon points="20,4 24,12 16,12" fill="#f59e0b" opacity="0.9"/>
      </g>
    </svg>`;

  return L.divIcon({
    html: `<div class="amb-marker-wrapper">${svg}</div>`,
    className: "",
    iconSize: [40, 40],
    iconAnchor: [20, 20],
  });
}

function makeHospitalIcon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" viewBox="0 0 36 36">
      <rect x="4" y="4" width="28" height="28" rx="6" fill="#0f172a" stroke="#22c55e" stroke-width="2"/>
      <rect x="15" y="9" width="6" height="18" rx="2" fill="#22c55e"/>
      <rect x="9" y="15" width="18" height="6" rx="2" fill="#22c55e"/>
    </svg>`;

  return L.divIcon({
    html: svg,
    className: "",
    iconSize: [36, 36],
    iconAnchor: [18, 18],
  });
}

const hospitalTrackerAmbulanceIcon = L.divIcon({
  className: "",
  html: `<div style="width:18px;height:18px;border-radius:50%;background:#ef4444;border:2px solid #fff;box-shadow:0 0 0 0 rgba(239,68,68,0.7);animation:amb-pulse 1.2s infinite;"></div>
  <style>@keyframes amb-pulse{0%{box-shadow:0 0 0 0 rgba(239,68,68,0.7)}70%{box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}}</style>`,
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

const hospitalTrackerHospitalIcon = L.divIcon({
  className: "",
  html: `<div style="width:28px;height:28px;border-radius:6px;background:#10b981;border:2px solid #fff;display:flex;align-items:center;justify-content:center;font-size:16px;color:#fff;font-weight:bold;box-shadow:0 2px 8px rgba(16,185,129,0.5);">+</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
});

function ETAChip({ eta, delta, confidence, congested, remainingKm, speed }) {
  if (eta == null) return null;

  const deltaStr = delta > 0 ? `+${delta}m` : delta < 0 ? `${delta}m` : null;
  const confPct = Math.round((confidence ?? 0.5) * 100);

  return (
    <div
      style={{
        position: "absolute",
        top: 16,
        left: "50%",
        transform: "translateX(-50%)",
        zIndex: 1000,
        pointerEvents: "none",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 8,
      }}
    >
      <div
        style={{
          background: "rgba(10,18,28,0.92)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(59,130,246,0.3)",
          borderRadius: 16,
          padding: "16px 32px",
          display: "flex",
          alignItems: "baseline",
          gap: 10,
          boxShadow: "0 8px 32px rgba(0,0,0,0.5)",
        }}
      >
        <span style={{ fontSize: 42, fontWeight: 900, color: "#f8fafc", fontFamily: "monospace", lineHeight: 1 }}>{eta}</span>
        <span style={{ fontSize: 16, color: "#94a3b8", fontWeight: 600, fontFamily: "monospace", alignSelf: "flex-end", paddingBottom: 4 }}>min</span>
        {deltaStr && (
          <span
            style={{
              fontSize: 14,
              fontWeight: 800,
              color: delta > 0 ? "#ef4444" : "#22c55e",
              fontFamily: "monospace",
              alignSelf: "flex-start",
              marginTop: 4,
            }}
          >
            {deltaStr}
          </span>
        )}
      </div>

      <div
        style={{
          display: "flex",
          gap: 12,
          alignItems: "center",
          background: "rgba(10,18,28,0.92)",
          borderRadius: 12,
          backdropFilter: "blur(8px)",
          padding: "8px 16px",
          border: "1px solid rgba(255,255,255,0.08)",
          boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
        }}
      >
        {remainingKm != null && (
          <span style={{ fontSize: 12, color: "#94a3b8", fontFamily: "monospace", fontWeight: 600 }}>{remainingKm.toFixed(1)} km left</span>
        )}
        {speed != null && speed > 1 && (
          <span style={{ fontSize: 12, color: "#64748b", fontFamily: "monospace" }}>· {Math.round(speed)} km/h</span>
        )}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: 8 }}>
          <div style={{ width: 60, height: 4, background: "#1e293b", borderRadius: 2, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${confPct}%`,
                background: "linear-gradient(90deg, #3b82f6, #06b6d4)",
                borderRadius: 2,
                transition: "width 0.6s ease",
              }}
            />
          </div>
          <span style={{ fontSize: 11, color: "#cbd5e1", fontFamily: "monospace", fontWeight: 600 }}>{confPct}%</span>
        </div>
      </div>

      {congested && (
        <div
          style={{
            background: "rgba(239,68,68,0.15)",
            border: "1px solid rgba(239,68,68,0.4)",
            borderRadius: 8,
            padding: "4px 12px",
            fontSize: 12,
            color: "#fca5a5",
            fontFamily: "monospace",
            fontWeight: 700,
            letterSpacing: "0.06em",
            backdropFilter: "blur(4px)",
          }}
        >
          ⚠ TRAFFIC DETECTED — ETA recalculated
        </div>
      )}
    </div>
  );
}

function BottomStatusBar({ currentStatus, onNextStatus }) {
  const steps = ["dispatched", "en_route", "on_scene", "arrived", "completed"];
  const currentIndex = steps.indexOf(currentStatus);
  const displayIndex = currentIndex === -1 ? 0 : currentIndex;

  const labels = {
    dispatched: "Dispatched",
    en_route: "En Route",
    on_scene: "On Scene",
    arrived: "Arrived",
    completed: "Completed",
  };

  const nextStatus = displayIndex < steps.length - 1 ? steps[displayIndex + 1] : null;

  const formatAction = (status) => {
    if (status === "en_route") return "Mark En Route";
    if (status === "on_scene") return "Mark On Scene";
    if (status === "arrived") return "Mark Arrived";
    if (status === "completed") return "Mark Completed";
    return "";
  };

  return (
    <div
      style={{
        padding: "20px 30px",
        background: "rgba(10,18,28,0.98)",
        borderTop: "1px solid #1e293b",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        zIndex: 500,
        flexShrink: 0,
        fontFamily: "monospace",
      }}
    >
      <div style={{ display: "flex", gap: "28px", alignItems: "center" }}>
        {steps.map((step, idx) => {
          const isPast = idx < displayIndex;
          const isCurrent = idx === displayIndex;
          const isFuture = idx > displayIndex;

          return (
            <div key={step} style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", opacity: isFuture ? 0.3 : 1 }}>
                <div
                  style={{
                    width: "16px",
                    height: "16px",
                    borderRadius: "50%",
                    background: isPast ? "#10b981" : isCurrent ? "#3b82f6" : "#334155",
                    boxShadow: isCurrent ? "0 0 0 4px rgba(59,130,246,0.2)" : "none",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {isPast && <span style={{ color: "#022c22", fontSize: "10px", fontWeight: "bold" }}>✓</span>}
                </div>
                <span style={{ fontSize: "13px", fontWeight: isCurrent ? 700 : 500, color: isCurrent ? "#f8fafc" : "#94a3b8" }}>
                  {labels[step]}
                </span>
              </div>
              {idx < steps.length - 1 && <div style={{ width: "24px", height: "2px", background: isPast ? "#10b981" : "#334155" }} />}
            </div>
          );
        })}
      </div>

      {nextStatus && (
        <button
          onClick={() => onNextStatus(nextStatus)}
          style={{
            padding: "12px 24px",
            borderRadius: "8px",
            background: "#3b82f6",
            border: "none",
            color: "white",
            fontSize: "14px",
            fontWeight: "bold",
            cursor: "pointer",
            fontFamily: "inherit",
            letterSpacing: "0.5px",
            boxShadow: "0 4px 12px rgba(59,130,246,0.3)",
          }}
        >
          {formatAction(nextStatus)} →
        </button>
      )}
    </div>
  );
}

function DispatchMapWidget({ state, navigate }) {
  const result = state?.result;
  const mapRef = useRef(null);
  const leafletRef = useRef(null);
  const markerRef = useRef(null);
  const routeLayerRef = useRef(null);
  const travelledLayerRef = useRef(null);
  const travelledCoordsRef = useRef([]);
  const prevPosRef = useRef(null);
  const targetPosRef = useRef(null);
  const animStartRef = useRef(null);
  const rafRef = useRef(null);

  const [eta, setEta] = useState(result?.eta_minutes ?? null);
  const [etaDelta, setEtaDelta] = useState(0);
  const [confidence, setConf] = useState(0.5);
  const [congested, setCongested] = useState(false);
  const [remainingKm, setRemaining] = useState(result?.distance_km ?? null);
  const [speed, setSpeed] = useState(null);
  const [wsStatus, setWsStatus] = useState("connecting");
  const [caseStatus, setCaseStatus] = useState("dispatched");

  const ambLat = state?.ambLat ?? result?.ambulance_lat ?? 30.3165;
  const ambLng = state?.ambLng ?? result?.ambulance_lng ?? 78.0322;
  const hosLat = result?.hospital_lat;
  const hosLng = result?.hospital_lng;
  const hospName = result?.hospital_name ?? "Destination";
  const caseId = result?.case_id;

  const wsBase = (() => {
    const env = import.meta.env.VITE_WS_URL;
    if (env) return env;
    const apiUrl = import.meta.env.VITE_API_URL || "";
    if (apiUrl) return apiUrl.replace(/^http/, "ws");
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}`;
  })();

  const apiBase = import.meta.env.VITE_API_URL || "";

  const handleNextStatus = async (newStatus) => {
    try {
      const token = localStorage.getItem("token");
      await fetch(`${apiBase}/api/cases/${caseId}/status`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status: newStatus, note: "App update" }),
      });
      setCaseStatus(newStatus);
    } catch (e) {
      console.error("Failed to update status", e);
    }
  };

  const animateTo = useCallback((toLatLng) => {
    if (!markerRef.current) return;
    const from = prevPosRef.current || toLatLng;
    prevPosRef.current = toLatLng;
    targetPosRef.current = toLatLng;
    animStartRef.current = performance.now();

    const bearing = bearingBetween(from[0], from[1], toLatLng[0], toLatLng[1]);
    markerRef.current.setIcon(makeAmbulanceIcon(bearing));

    travelledCoordsRef.current.push(toLatLng);
    travelledLayerRef.current?.setLatLngs(travelledCoordsRef.current);

    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    const tick = (now) => {
      if (!markerRef.current || !prevPosRef.current) return;
      const t = Math.min(1, (now - animStartRef.current) / LERP_DURATION_MS);
      markerRef.current.setLatLng([lerp(from[0], toLatLng[0], t), lerp(from[1], toLatLng[1], t)]);
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  }, []);

  useEffect(() => {
    if (!mapRef.current || leafletRef.current || !result) return;

    const map = L.map(mapRef.current, {
      center: [ambLat, ambLng],
      zoom: 13,
      zoomControl: true,
    });

    L.tileLayer(TILE_URL, { attribution: TILE_ATTR }).addTo(map);
    leafletRef.current = map;

    if (hosLat && hosLng) {
      L.marker([hosLat, hosLng], { icon: makeHospitalIcon() })
        .addTo(map)
        .bindPopup(
          `<div style="text-align:center; padding: 4px;">
            <div style="font-weight:bold; font-size: 14px; margin-bottom:4px; color:#f8fafc;">${hospName}</div>
            <div style="color: #64748b; font-size: 11px;">${result.address || "Medical Facility"}</div>
          </div>`,
          { closeButton: false }
        )
        .openPopup();
    }

    prevPosRef.current = [ambLat, ambLng];
    targetPosRef.current = [ambLat, ambLng];
    markerRef.current = L.marker([ambLat, ambLng], { icon: makeAmbulanceIcon(0) }).addTo(map);
    routeLayerRef.current = L.polyline([], { color: "#475569", weight: 3, opacity: 0.8, dashArray: "10, 10" }).addTo(map);
    travelledLayerRef.current = L.polyline([], { color: "#0ea5e9", weight: 5, opacity: 1, dashArray: "15, 5" }).addTo(map);

    if (hosLat && hosLng) {
      map.fitBounds([[ambLat, ambLng], [hosLat, hosLng]], { padding: [40, 40] });
    }

    return () => {
      map.remove();
      leafletRef.current = null;
    };
  }, [ambLat, ambLng, hosLat, hosLng, hospName, result]);

  useEffect(() => {
    if (!caseId) return undefined;
    const token = localStorage.getItem("token");
    if (!token) return undefined;

    const ws = new WebSocket(`${wsBase}/ws/track/${caseId}?token=${token}`);
    let alive = true;

    ws.onopen = () => setWsStatus("live");
    ws.onerror = () => setWsStatus("error");
    ws.onclose = () => {
      if (alive) setWsStatus("disconnected");
    };

    ws.onmessage = (e) => {
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch {
        return;
      }

      if (msg.type === "route_init") {
        const latlngs = (msg.coords || []).map(([lng, lat]) => [lat, lng]);
        routeLayerRef.current?.setLatLngs(latlngs);
        if (leafletRef.current && latlngs.length > 1) {
          leafletRef.current.fitBounds(L.latLngBounds(latlngs), { padding: [40, 40] });
        }
        setEta(msg.eta_minutes);
        setConf(msg.confidence ?? 0.5);
      }

      if (msg.type === "position") {
        animateTo([msg.lat, msg.lng]);
        leafletRef.current?.panTo([msg.lat, msg.lng], { animate: true, duration: 1.5 });
        if (msg.eta_minutes != null) setEta(msg.eta_minutes);
        if (msg.delta_minutes != null) setEtaDelta(msg.delta_minutes);
        if (msg.confidence != null) setConf(msg.confidence);
        if (msg.congested != null) setCongested(msg.congested);
        if (msg.remaining_km != null) setRemaining(msg.remaining_km);
        if (msg.observed_speed_kmh != null) setSpeed(msg.observed_speed_kmh);
      }

      if (msg.type === "status_change") {
        setCaseStatus(msg.status);
        if (["arrived", "completed"].includes(msg.status)) setWsStatus("arrived");
      }
    };

    return () => {
      alive = false;
      ws.close();
    };
  }, [animateTo, caseId, wsBase]);

  useEffect(() => {
    if (!navigator.geolocation || !caseId) return undefined;
    const token = localStorage.getItem("token");
    if (!token) return undefined;

    const ws = new WebSocket(`${wsBase}/ws/track/${caseId}?token=${token}`);
    let watchId = null;

    ws.onopen = () => {
      watchId = navigator.geolocation.watchPosition(
        (pos) => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(
              JSON.stringify({
                type: "ping",
                lat: pos.coords.latitude,
                lng: pos.coords.longitude,
                speed_kmh: pos.coords.speed ? pos.coords.speed * 3.6 : undefined,
              })
            );
          }
        },
        null,
        { enableHighAccuracy: true, maximumAge: 0 }
      );
    };

    return () => {
      if (watchId != null) navigator.geolocation.clearWatch(watchId);
      ws.close();
    };
  }, [caseId, wsBase]);

  useEffect(() => () => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }, []);

  if (!result) {
    return (
      <div style={{ padding: 40, color: "#94a3b8", textAlign: "center" }}>
        No dispatch result.{" "}
        <button onClick={() => navigate("/dispatch")} style={{ color: "#60a5fa", background: "none", border: "none", cursor: "pointer" }}>
          Return to dispatch
        </button>
      </div>
    );
  }

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#060d1a" }}>
      <div
        style={{
          padding: "12px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          borderBottom: "1px solid #1e293b",
          background: "rgba(10,18,28,0.98)",
          zIndex: 500,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 16 }}>🚑</span>
          <span style={{ fontSize: 13, fontFamily: "monospace", color: "#e2e8f0", letterSpacing: "0.1em", fontWeight: 700 }}>
            TRACKING — {hospName}
          </span>
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: "50%",
              display: "inline-block",
              marginLeft: 8,
              background: wsStatus === "live" ? "#10b981" : wsStatus === "arrived" ? "#3b82f6" : wsStatus === "error" ? "#ef4444" : "#f59e0b",
              boxShadow: wsStatus === "live" ? "0 0 0 4px rgba(16,185,129,0.2)" : "none",
              animation: wsStatus === "live" ? "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite" : "none",
            }}
          />
          <span style={{ fontSize: 11, fontFamily: "monospace", color: "#64748b", fontWeight: 600 }}>
            {wsStatus === "live" ? "LIVE" : wsStatus.toUpperCase()}
          </span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <span
            style={{
              padding: "4px 10px",
              borderRadius: "12px",
              background: "rgba(148,163,184,0.1)",
              color: "#94a3b8",
              fontSize: 11,
              fontFamily: "monospace",
              fontWeight: 700,
              border: "1px solid rgba(148,163,184,0.2)",
            }}
          >
            CASE {caseId || "---"}
          </span>
          <button
            onClick={() => navigate(-1)}
            style={{
              padding: "6px 16px",
              borderRadius: 8,
              fontSize: 12,
              background: "rgba(51,65,85,0.3)",
              border: "1px solid #334155",
              color: "#e2e8f0",
              cursor: "pointer",
              fontFamily: "monospace",
              fontWeight: 600,
              transition: "0.2s",
            }}
          >
            ← Back
          </button>
        </div>
      </div>

      <div style={{ flex: 1, position: "relative" }}>
        <ETAChip eta={eta} delta={etaDelta} confidence={confidence} congested={congested} remainingKm={remainingKm} speed={speed} />
        <div id="map" ref={mapRef} style={{ width: "100%", height: "100%", paddingTop: 56 }} />
      </div>

      <BottomStatusBar currentStatus={caseStatus} onNextStatus={handleNextStatus} />

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.6; transform: scale(1.2); }
        }
        @keyframes pulseRing {
          0% { transform: scale(0.8); opacity: 0.8; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        .amb-marker-wrapper {
          position: relative;
          display: flex;
          justify-content: center;
          align-items: center;
          width: 40px;
          height: 40px;
        }
        .amb-marker-wrapper::before {
          content: "";
          position: absolute;
          width: 100%;
          height: 100%;
          border-radius: 50%;
          border: 2px solid #3b82f6;
          animation: pulseRing 1.5s ease-out infinite;
          box-sizing: border-box;
          pointer-events: none;
        }
        .leaflet-container { background: #060d1a !important; }
        .leaflet-popup-content-wrapper {
          background: rgba(10,18,28,0.92) !important;
          backdrop-filter: blur(8px);
          border: 1px solid #1e293b;
          color: #e2e8f0;
          border-radius: 12px !important;
          font-family: monospace;
          box-shadow: 0 8px 32px rgba(0,0,0,0.5) !important;
        }
        .leaflet-popup-tip { background: rgba(10,18,28,0.92) !important; display: none; }
      `}</style>
    </div>
  );
}

function HospitalMapWidget({ hospitalPosition, ambulancePosition, caseData, eta }) {
  const mapCenter = ambulancePosition
    ? [(ambulancePosition[0] + hospitalPosition[0]) / 2, (ambulancePosition[1] + hospitalPosition[1]) / 2]
    : hospitalPosition;

  return (
    <div style={{ height: 360, borderRadius: 4, overflow: "hidden", border: "1px solid #00aa2a", marginBottom: "1rem" }}>
      <MapContainer center={mapCenter} zoom={13} style={{ width: "100%", height: "100%" }} zoomControl>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        <Marker position={hospitalPosition} icon={hospitalTrackerHospitalIcon}>
          <Popup>{caseData.hospital_name || "Your Hospital"}</Popup>
        </Marker>
        {ambulancePosition && (
          <>
            <Marker position={ambulancePosition} icon={hospitalTrackerAmbulanceIcon}>
              <Popup>Ambulance — ETA {eta} min</Popup>
            </Marker>
            <Polyline positions={[ambulancePosition, hospitalPosition]} color="#ef4444" weight={2} dashArray="6,6" opacity={0.7} />
          </>
        )}
      </MapContainer>
      {!ambulancePosition && (
        <div
          style={{
            position: "relative",
            marginTop: "-48px",
            display: "flex",
            justifyContent: "center",
            pointerEvents: "none",
            zIndex: 500,
          }}
        >
          <div style={{ color: "#ffff00", fontFamily: "'Courier New', monospace", fontSize: 12, background: "rgba(0,0,0,0.7)", padding: "8px 12px", borderRadius: 4 }}>
            Waiting for ambulance GPS...
          </div>
        </div>
      )}
    </div>
  );
}

export default function MapWidget(props) {
  if (props.variant === "hospital") {
    return <HospitalMapWidget {...props} />;
  }

  return <DispatchMapWidget {...props} />;
}
