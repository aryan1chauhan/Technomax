import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, Navigate } from 'react-router-dom';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

// ⚠️ USER MUST REPLACE THIS IF THEY DON'T USE ORS
mapboxgl.accessToken = import.meta.env.VITE_MAPBOX_TOKEN || "YOUR_MAPBOX_TOKEN";

const fetchRoute = async (start, end) => {
  const key = import.meta.env.VITE_ORS_API_KEY;
  if (!key) return null;
  const url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${key}&start=${start[0]},${start[1]}&end=${end[0]},${end[1]}`;
  try {
    const res = await fetch(url);
    const json = await res.json();
    if (json.features && json.features.length > 0) {
      return json.features[0].geometry.coordinates;
    }
    return null;
  } catch (err) {
    console.error('Route fetch failed:', err);
    return null;
  }
};

export default function SystemMap() {
  const location = useLocation();
  const navigate = useNavigate();
  const data = location.state;

  if (!data) return <Navigate to="/dispatch" replace />;

  const mapContainer = useRef(null);
  const map = useRef(null);
  const ambulanceMarker = useRef(null);
  const hospitalMarker = useRef(null);
  const wsRef = useRef(null);
  
  const startPos = [data.ambulance_lng || 77.888, data.ambulance_lat || 29.8543];
  const endPos = [data.lng || 77.89, data.lat || 29.85];

  const [simulationLogs, setSimulationLogs] = useState([]);
  const [eta, setEta] = useState(data.eta_minutes || 0);
  const [distance, setDistance] = useState(data.distance_km || "--");

  useEffect(() => {
    let reconnectTimer;
    const connectWebSocket = () => {
      const socket = new WebSocket(`ws://localhost:8000/ws/ambulance/${data.case_id}`);
      socket.onopen = () => console.log("WS connected (Ambulance -> Hospital)");
      socket.onerror = (e) => console.error("WS error", e);
      socket.onclose = () => {
        console.log("WS closed, attempting reconnect in 3s...");
        reconnectTimer = setTimeout(connectWebSocket, 2000);
      };
      wsRef.current = socket;
    };
    if (data.case_id) connectWebSocket();
    
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [data.case_id]);

  useEffect(() => {
    if (map.current) return;
    
    if (!document.getElementById('mapbox-custom-styles')) {
      const style = document.createElement('style');
      style.id = 'mapbox-custom-styles';
      style.innerHTML = `
        .pulse-marker {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #ef4444;
          box-shadow: 0 0 15px #ef4444;
          animation: pulse 1s infinite;
        }
        @keyframes pulse {
          0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
          70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
          100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .hospital-marker {
          width: 28px;
          height: 28px;
          background-image: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="%2310b981"><path d="M19 3H5c-1.1 0-1.99.9-1.99 2L3 19c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-8 13h-2v-3H6v-2h3V8h2v3h3v2h-3v3z"/></svg>');
          background-size: cover;
          filter: drop-shadow(0 0 8px #10b981);
        }
      `;
      document.head.appendChild(style);
    }

    try {
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: "mapbox://styles/mapbox/dark-v11",
        center: startPos,
        zoom: 13,
        pitch: 45,
      });

      const el = document.createElement('div');
      el.className = 'pulse-marker';

      const hospEl = document.createElement('div');
      hospEl.className = 'hospital-marker';

      map.current.on('load', async () => {
        hospitalMarker.current = new mapboxgl.Marker(hospEl)
          .setLngLat(endPos)
          .addTo(map.current);

        ambulanceMarker.current = new mapboxgl.Marker(el)
          .setLngLat(startPos)
          .addTo(map.current);

        const routeCoords = await fetchRoute(startPos, endPos);
        
        if (routeCoords && routeCoords.length > 0) {
          map.current.addSource('route', {
            type: 'geojson',
            data: {
              type: 'Feature',
              properties: {},
              geometry: {
                type: 'LineString',
                coordinates: routeCoords
              }
            }
          });

          map.current.addLayer({
            id: 'route-glow',
            type: 'line',
            source: 'route',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: { 'line-color': '#ef4444', 'line-width': 8, 'line-opacity': 0.3 }
          });
          
          map.current.addLayer({
            id: 'route',
            type: 'line',
            source: 'route',
            layout: { 'line-join': 'round', 'line-cap': 'round' },
            paint: { 'line-color': '#ef4444', 'line-width': 3 }
          });

          const bounds = routeCoords.reduce((b, coord) => b.extend(coord), new mapboxgl.LngLatBounds(routeCoords[0], routeCoords[0]));
          map.current.fitBounds(bounds, { padding: 60, pitch: 45 });

          let index = 0;
          const totalPoints = routeCoords.length;

          const moveAmbulance = () => {
            if (index < totalPoints && ambulanceMarker.current && map.current) {
              const currentCoord = routeCoords[index];
              ambulanceMarker.current.setLngLat(currentCoord);
              
              map.current.panTo(currentCoord, { duration: 1000, essential: true });
              
              const remaining = totalPoints - index;
              if (data.eta_minutes) {
                const newEta = Math.max(1, Math.round((remaining / totalPoints) * data.eta_minutes));
                setEta(newEta);
                
                // Broadcast live location seamlessly
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({
                    case_id: data.case_id,
                    lat: currentCoord[1],
                    lng: currentCoord[0],
                    eta_minutes: newEta,
                    timestamp: Date.now()
                  }));
                }
              }

              index++;
              setTimeout(moveAmbulance, 1000); 
            } else {
              setEta(0); 
            }
          };
          
          setTimeout(moveAmbulance, 2500);
        } else {
           const bounds = new mapboxgl.LngLatBounds(startPos, startPos).extend(endPos);
           map.current.fitBounds(bounds, { padding: 60 });
        }
      });
    } catch (err) {
      console.error("Mapbox init err. Invalid Token? ", err);
    }

  }, [data, endPos, startPos]);

  useEffect(() => {
    const interval = setInterval(() => {
      const cases = ["Head Injury", "Cardiac Arrest", "Major Trauma", "Resp. Failure", "Severe Burn"];
      const locations = ["Sector 7, Main Rd", "Highway 42, Mile 18", "Downtown Square", "Industrial Park B"];
      const randomCase = cases[Math.floor(Math.random() * cases.length)];
      const randomLoc = locations[Math.floor(Math.random() * locations.length)];
      
      const logMsg = `[SYS] Triage Event: ${randomCase} at ${randomLoc}. Assigning unit...`;
      setSimulationLogs(prev => [logMsg, ...prev].slice(0, 5));
      
    }, 8000); 
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ height: '100vh', width: '100vw', background: '#0a0a0a', display: 'flex', flexDirection: 'column', fontFamily: 'system-ui, sans-serif' }}>
      
      <div style={{ padding: '15px 20px', background: 'rgba(15, 23, 42, 0.95)', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', zIndex: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
          <button onClick={() => navigate(-1)} style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px', color: '#fff', cursor: 'pointer', padding: '4px 12px', fontSize: '1rem', transition: 'all 0.2s' }}>
            ← Back
          </button>
          <h1 style={{ margin: 0, fontSize: '1.25rem', color: '#fff', fontWeight: '700', letterSpacing: '0.05em' }}>SYSTEM COMMAND</h1>
          <span style={{ padding: '4px 8px', background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', borderRadius: '4px', fontSize: '0.75rem', fontWeight: 'bold', border: '1px solid rgba(239,68,68,0.3)', letterSpacing: '1px' }}>
            ● LIVE TRACKING
          </span>
        </div>
        <div style={{ color: '#94a3b8', fontSize: '0.85rem', fontWeight: 500 }}>
          ACTIVE CASE: <span style={{ color: '#fff', marginLeft: '4px' }}>#{data.case_id || 'SYS-001'}</span>
        </div>
      </div>

      <div style={{ flex: 1, position: 'relative' }}>
        <div ref={mapContainer} style={{ width: '100%', height: '100%' }} />

        <div style={{ position: 'absolute', top: '20px', right: '20px', background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '20px', color: '#fff', width: '240px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px', fontWeight: 600 }}>Target Hospital</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '15px', color: '#fff' }}>{data.hospital_name || 'Destination'}</div>
          
          <div style={{ color: '#94a3b8', fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '4px', fontWeight: 600 }}>Estimated Arrival</div>
          <div style={{ fontSize: '3rem', fontWeight: 800, color: eta === 0 ? '#10b981' : '#3b82f6', lineHeight: 1, textShadow: eta === 0 ? '0 0 20px rgba(16,185,129,0.4)' : '0 0 20px rgba(59,130,246,0.4)' }}>
            {eta === 0 ? 'ARRIVED' : `${eta}`}
            {eta !== 0 && <span style={{ fontSize: '1rem', color: '#94a3b8', marginLeft: '6px', fontWeight: 600 }}>min</span>}
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600, letterSpacing: '0.5px' }}>SPEED</div>
              <div style={{ fontWeight: 'bold', color: '#f8fafc', fontSize: '0.9rem' }}>{eta === 0 ? '0' : '40'} km/h</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: 600, letterSpacing: '0.5px' }}>DISTANCE</div>
              <div style={{ fontWeight: 'bold', color: '#f8fafc', fontSize: '0.9rem' }}>{distance} km</div>
            </div>
          </div>
        </div>

        <div style={{ position: 'absolute', bottom: '24px', left: '24px', background: 'rgba(15, 23, 42, 0.85)', backdropFilter: 'blur(12px)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '16px', padding: '16px', color: '#fff', width: '380px', boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5)', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}>
          <div style={{ color: '#10b981', fontSize: '0.8rem', marginBottom: '12px', fontWeight: 'bold', borderBottom: '1px solid rgba(16, 185, 129, 0.2)', paddingBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ display: 'inline-block', width: '6px', height: '6px', background: '#10b981', borderRadius: '50%', boxShadow: '0 0 8px #10b981' }}></span>
            ACTIVE NETWORK LOGS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.8rem' }}>
            {simulationLogs.length === 0 && <span style={{ color: '#64748b', fontStyle: 'italic' }}>Monitoring incoming dispatch streams...</span>}
            {simulationLogs.map((log, i) => (
              <div key={i} style={{ color: i === 0 ? '#f8fafc' : '#64748b', opacity: 1 - (i * 0.15), whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontWeight: i === 0 ? 500 : 400 }}>
                {log}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
