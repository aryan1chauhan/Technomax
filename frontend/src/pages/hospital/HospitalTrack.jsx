import { useState, useEffect, useRef } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, ZoomControl } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import api from '../../api/axios'

// Fix Leaflet default icon bug
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

const ambulanceIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
})

const hospitalIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
})

const HOSPITAL_POS = [29.8700, 77.8960]

const calculateDistance = (pos1, pos2) => {
  if (!pos1 || !pos2) return null
  const R = 6371
  const lat1 = (pos1[0] * Math.PI) / 180
  const lat2 = (pos2[0] * Math.PI) / 180
  const dlat = ((pos2[0] - pos1[0]) * Math.PI) / 180
  const dlng = ((pos2[1] - pos1[1]) * Math.PI) / 180
  const a = Math.sin(dlat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlng / 2) ** 2
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return (R * c).toFixed(2)
}

function FlyToAmbulance({ position }) {
  const map = useMap()
  useEffect(() => {
    if (position) map.flyTo(position, 15, { animate: true, duration: 1 })
  }, [position, map])
  return null
}

/* ── Terminal Design Tokens ────────────────────────────── */
const T = {
  bg:      '#0a0a0a',
  green:   '#00ff41',
  gray:    '#888888',
  red:     '#ff3333',
  dim:     '#333333',
  border:  '#00ff41',
}

export default function HospitalTrack() {
  const { case_id } = useParams()
  const location = useLocation()
  const navigate = useNavigate()

  const [caseData, setCaseData] = useState(location.state || null)
  const [loading, setLoading] = useState(!location.state)
  const [ambulancePos, setAmbulancePos] = useState(null)
  const [etaMinutes, setEtaMinutes] = useState(caseData?.eta_minutes || '--')
  const [connected, setConnected] = useState(false)
  const [arrived, setArrived] = useState(false)
  const [checklist, setChecklist] = useState([false, false, false, false])

  const wsRef = useRef(null)

  // Fetch case data if not passed via location.state
  useEffect(() => {
    if (caseData) return
    const fetchCase = async () => {
      try {
        const res = await api.get('/api/cases/')
        const found = res.data.find(c => c.id === parseInt(case_id))
        if (found) {
          setCaseData(found)
          setAmbulancePos([found.ambulance_lat, found.ambulance_lng])
          setEtaMinutes(found.eta_minutes)
        }
      } catch (err) {
        console.error('Error fetching case:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchCase()
  }, [case_id])

  // WebSocket — connect to hospital channel
  useEffect(() => {
    if (!case_id) return

    let reconnectTimer = null
    let destroyed = false

    const connectWS = () => {
      if (destroyed) return
      const ws = new WebSocket(`ws://localhost:8000/ws/hospital/${case_id}`)
      wsRef.current = ws

      ws.onopen = () => setConnected(true)

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.lat && data.lng) {
          setAmbulancePos([data.lat, data.lng])
          setEtaMinutes(data.eta_minutes)
          if (data.eta_minutes === 0) setArrived(true)
        }
      }

      ws.onerror = (err) => {
        console.error('WebSocket error:', err)
      }

      ws.onclose = () => {
        setConnected(false)
        if (!destroyed) {
          console.log('WS closed — reconnecting in 2s...')
          reconnectTimer = setTimeout(connectWS, 2000)
        }
      }
    }

    connectWS()

    return () => {
      destroyed = true
      clearTimeout(reconnectTimer)
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
      }
    }
  }, [case_id])

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const toggleChecklist = (idx) => {
    setChecklist(prev => {
      const next = [...prev]
      next[idx] = !next[idx]
      return next
    })
  }

  const checklistItems = [
    'Alert trauma team',
    'Prepare equipment',
    'Clear emergency bay',
    'Notify on-call doctor',
  ]

  const liveDistance = ambulancePos ? calculateDistance(ambulancePos, HOSPITAL_POS) : caseData?.distance_km || '--'

  /* ── Loading State ──────────────────────────────────── */
  if (loading) {
    return (
      <div style={{
        backgroundColor: T.bg, color: T.green, fontFamily: 'monospace',
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '16px',
      }}>
        <span className="term-blink">LOADING CASE DATA...</span>
      </div>
    )
  }

  if (!caseData) {
    return (
      <div style={{
        backgroundColor: T.bg, color: T.red, fontFamily: 'monospace',
        minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '16px',
      }}>
        ERROR: CASE #{case_id} NOT FOUND
      </div>
    )
  }

  const center = ambulancePos
    ? [(ambulancePos[0] + HOSPITAL_POS[0]) / 2, (ambulancePos[1] + HOSPITAL_POS[1]) / 2]
    : HOSPITAL_POS

  return (
    <>
      {/* ── CSS ──────────────────────────────────────── */}
      <style>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50%      { opacity: 0; }
        }
        @keyframes pulse-green {
          0%, 100% { opacity: 1; box-shadow: 0 0 4px ${T.green}; }
          50%      { opacity: .45; box-shadow: 0 0 12px ${T.green}; }
        }
        @keyframes scanline {
          0%   { background-position: 0 0; }
          100% { background-position: 0 100%; }
        }
        .term-blink  { animation: blink 1s step-end infinite; }
        .term-pulse  { animation: pulse-green 1.6s ease-in-out infinite; }

        .term-box {
          border: 1px solid ${T.green};
          background: ${T.bg};
        }

        /* override leaflet inside terminal */
        .terminal-map .leaflet-container {
          height: 100%; width: 100%;
          background: ${T.bg} !important;
        }
        .terminal-map .leaflet-control-zoom a {
          background: ${T.bg} !important;
          color: ${T.green} !important;
          border-color: ${T.green} !important;
        }
        .terminal-map .leaflet-control-attribution {
          background: rgba(10,10,10,.85) !important;
          color: ${T.gray} !important;
          font-family: monospace !important;
          font-size: 9px !important;
        }
        .terminal-map .leaflet-popup-content-wrapper {
          background: ${T.bg} !important;
          color: ${T.green} !important;
          border: 1px solid ${T.green} !important;
          border-radius: 0 !important;
          font-family: monospace !important;
          box-shadow: none !important;
        }
        .terminal-map .leaflet-popup-tip {
          background: ${T.bg} !important;
          border: 1px solid ${T.green} !important;
          box-shadow: none !important;
        }

        /* checklist hover */
        .term-check:hover { background: rgba(0,255,65,.08); }

        /* scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: ${T.bg}; }
        ::-webkit-scrollbar-thumb { background: ${T.dim}; }
      `}</style>

      <div style={{
        backgroundColor: T.bg,
        color: T.green,
        fontFamily: "'Courier New', Courier, monospace",
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        fontSize: '14px',
        lineHeight: '1.5',
      }}>

        {/* ╔══════════════════════════════════════════╗
            ║  HEADER                                  ║
            ╚══════════════════════════════════════════╝ */}
        <div style={{
          borderBottom: `1px solid ${T.green}`,
          padding: '12px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          {/* Left — back + emergency label */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <button
              onClick={() => navigate('/hospital/dashboard')}
              style={{
                background: 'none', border: 'none', color: T.gray,
                fontFamily: 'inherit', fontSize: '14px', cursor: 'pointer',
                padding: 0,
              }}
              onMouseEnter={e => e.target.style.color = T.green}
              onMouseLeave={e => e.target.style.color = T.gray}
            >
              ← BACK
            </button>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {/* blinking red dot */}
                <span style={{
                  display: 'inline-block', width: '10px', height: '10px',
                  borderRadius: '50%', backgroundColor: T.red,
                }} className="term-blink" />
                <span style={{ color: T.red, fontWeight: 'bold', fontSize: '16px', letterSpacing: '1px' }}>
                  INCOMING EMERGENCY
                </span>
              </div>
              <div style={{ color: T.gray, marginTop: '2px' }}>
                Case #{case_id} — {(caseData.condition || 'Unknown').toUpperCase()}
              </div>
            </div>
          </div>

          {/* Right — connection + logout */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <span style={{
              color: connected ? T.green : T.red,
              fontSize: '12px', letterSpacing: '1px',
            }}>
              {connected ? '● CONNECTED' : '○ DISCONNECTED'}
            </span>
            <button
              onClick={handleLogout}
              style={{
                background: 'none', border: `1px solid ${T.dim}`,
                color: T.gray, fontFamily: 'inherit', fontSize: '12px',
                cursor: 'pointer', padding: '4px 12px',
              }}
              onMouseEnter={e => { e.target.style.borderColor = T.red; e.target.style.color = T.red }}
              onMouseLeave={e => { e.target.style.borderColor = T.dim; e.target.style.color = T.gray }}
            >
              LOGOUT
            </button>
          </div>
        </div>

        {/* ╔══════════════════════════════════════════╗
            ║  MAIN CONTENT                            ║
            ╚══════════════════════════════════════════╝ */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'row',
          overflow: 'hidden',
        }}>
          {/* ── LEFT: Map + Stats ─────────────────── */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>

            {/* MAP */}
            <div className="terminal-map" style={{
              flex: 1, position: 'relative', minHeight: '300px',
              borderBottom: `1px solid ${T.green}`,
            }}>
              <MapContainer center={center} zoom={14} zoomControl={false} style={{ width: '100%', height: '100%' }}>
                <TileLayer
                  attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                  url="https://{s}.basemaps.cartocdn.com/dark_matter/{z}/{x}/{y}{r}.png"
                />
                <ZoomControl position="bottomright" />
                <Marker position={HOSPITAL_POS} icon={hospitalIcon}>
                  <Popup>🏥 YOUR HOSPITAL</Popup>
                </Marker>
                {ambulancePos && (
                  <>
                    <FlyToAmbulance position={ambulancePos} />
                    <Marker position={ambulancePos} icon={ambulanceIcon}>
                      <Popup>🚑 {arrived ? 'ARRIVED' : 'EN ROUTE'}</Popup>
                    </Marker>
                    <Polyline
                      positions={[ambulancePos, HOSPITAL_POS]}
                      pathOptions={{
                        color: '#3B82F6', weight: 3, opacity: 0.9,
                        dashArray: '8, 6', lineCap: 'square',
                      }}
                    />
                  </>
                )}
              </MapContainer>

              {/* GPS waiting overlay */}
              {!ambulancePos && (
                <div style={{
                  position: 'absolute', inset: 0, zIndex: 1000,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: 'rgba(10,10,10,.75)',
                  flexDirection: 'column', gap: '8px',
                }}>
                  <span className="term-blink" style={{ fontSize: '18px', color: T.green }}>
                    SCANNING...
                  </span>
                  <span style={{ color: T.gray, fontSize: '12px' }}>
                    WAITING FOR AMBULANCE GPS SIGNAL
                  </span>
                </div>
              )}
            </div>

            {/* ── STATS ROW ──────────────────────────── */}
            <div style={{
              borderBottom: `1px solid ${T.green}`,
              padding: '12px 20px',
              display: 'flex',
              alignItems: 'center',
              flexShrink: 0,
              gap: '0',
            }}>
              <div style={{ flex: 1 }}>
                <span style={{ color: T.gray }}>ETA: </span>
                <span style={{ color: arrived ? T.green : T.red, fontWeight: 'bold' }}>
                  {arrived ? 'ARRIVED' : `${etaMinutes} min`}
                </span>
              </div>
              <span style={{ color: T.dim, margin: '0 12px' }}>│</span>
              <div style={{ flex: 1 }}>
                <span style={{ color: T.gray }}>Distance: </span>
                <span style={{ fontWeight: 'bold' }}>{liveDistance} km</span>
              </div>
              <span style={{ color: T.dim, margin: '0 12px' }}>│</span>
              <div style={{ flex: 1 }}>
                <span style={{ color: T.gray }}>Condition: </span>
                <span style={{ color: T.red, fontWeight: 'bold' }}>
                  {(caseData.condition || 'N/A').toUpperCase()}
                </span>
              </div>
            </div>

            {/* ── EQUIPMENT ──────────────────────────── */}
            <div style={{
              borderBottom: `1px solid ${T.green}`,
              padding: '12px 20px',
              flexShrink: 0,
            }}>
              <span style={{ color: T.gray }}>Equipment Needed: </span>
              {caseData.equipment_needed?.length > 0 ? (
                caseData.equipment_needed.map(eq => (
                  <span key={eq} style={{ color: T.green, marginRight: '8px' }}>
                    [{eq.replace('_', ' ').toUpperCase()}]
                  </span>
                ))
              ) : (
                <span style={{ color: T.dim }}>[NONE]</span>
              )}
            </div>

            {/* ── STATUS BAR ─────────────────────────── */}
            <div style={{
              padding: '10px 20px',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              flexShrink: 0,
            }}>
              {!ambulancePos ? (
                <>
                  <span style={{
                    display: 'inline-block', width: '8px', height: '8px',
                    borderRadius: '50%', backgroundColor: T.gray,
                  }} className="term-blink" />
                  <span className="term-blink" style={{ color: T.gray }}>
                    WAITING FOR GPS...
                  </span>
                </>
              ) : arrived ? (
                <>
                  <span style={{
                    display: 'inline-block', width: '8px', height: '8px',
                    borderRadius: '50%', backgroundColor: T.green,
                    boxShadow: `0 0 8px ${T.green}`,
                  }} />
                  <span style={{ color: T.green, fontWeight: 'bold', letterSpacing: '2px' }}>
                    ■ ARRIVED
                  </span>
                </>
              ) : (
                <>
                  <span style={{
                    display: 'inline-block', width: '8px', height: '8px',
                    borderRadius: '50%', backgroundColor: T.green,
                  }} className="term-pulse" />
                  <span style={{ color: T.green }}>
                    En Route → Your Hospital
                  </span>
                </>
              )}
            </div>
          </div>

          {/* ── RIGHT PANEL: Preparation Checklist ──── */}
          <div style={{
            width: '300px',
            borderLeft: `1px solid ${T.green}`,
            display: 'flex',
            flexDirection: 'column',
            flexShrink: 0,
          }}>
            {/* Panel header */}
            <div style={{
              padding: '12px 16px',
              borderBottom: `1px solid ${T.green}`,
              letterSpacing: '1px',
              fontSize: '13px',
              color: T.gray,
            }}>
              ┌─ PREPARATION CHECKLIST ─┐
            </div>

            {/* Checklist items */}
            <div style={{ padding: '8px 0', flex: 1 }}>
              {checklistItems.map((item, idx) => (
                <button
                  key={idx}
                  onClick={() => toggleChecklist(idx)}
                  className="term-check"
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    background: 'none',
                    border: 'none',
                    fontFamily: 'inherit',
                    fontSize: '14px',
                    padding: '10px 16px',
                    cursor: 'pointer',
                    color: checklist[idx] ? T.green : T.gray,
                    transition: 'background .15s',
                  }}
                >
                  <span style={{ marginRight: '8px' }}>
                    {checklist[idx] ? '[X]' : '[ ]'}
                  </span>
                  <span style={{
                    textDecoration: checklist[idx] ? 'line-through' : 'none',
                  }}>
                    {item}
                  </span>
                </button>
              ))}
            </div>

            {/* Progress */}
            <div style={{
              padding: '12px 16px',
              borderTop: `1px solid ${T.green}`,
              fontSize: '12px',
              color: T.gray,
            }}>
              └─ {checklist.filter(Boolean).length}/{checklist.length} COMPLETE ─┘
            </div>

            {/* ── CASE META ──────────────────────────── */}
            <div style={{
              borderTop: `1px solid ${T.green}`,
              padding: '12px 16px',
              fontSize: '12px',
              lineHeight: '1.8',
            }}>
              <div style={{ color: T.gray, letterSpacing: '1px', marginBottom: '6px' }}>
                ┌─ CASE DETAILS ─┐
              </div>
              <div>
                <span style={{ color: T.gray }}>ID:        </span>
                <span>{case_id}</span>
              </div>
              <div>
                <span style={{ color: T.gray }}>Hospital:  </span>
                <span>{caseData.hospital_name || 'N/A'}</span>
              </div>
              <div>
                <span style={{ color: T.gray }}>Score:     </span>
                <span>{caseData.score != null ? caseData.score : 'N/A'}</span>
              </div>
              <div>
                <span style={{ color: T.gray }}>Severity:  </span>
                <span style={{ color: T.red }}>
                  {(caseData.severity || caseData.condition || 'N/A').toUpperCase()}
                </span>
              </div>
              <div>
                <span style={{ color: T.gray }}>WebSocket: </span>
                <span style={{ color: connected ? T.green : T.red }}>
                  {connected ? 'ACTIVE' : 'CLOSED'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
