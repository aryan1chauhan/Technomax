import { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate, Navigate } from 'react-router-dom'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, ZoomControl } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

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

// Map ref stored globally so FlyToLocation can access it
const mapInstanceRef = { current: null }

function FlyToLocation({ position, heading }) {
  const map = useMap()

  useEffect(() => {
    if (!map) return
    mapInstanceRef.current = map
  }, [map])

  useEffect(() => {
    if (position) {
      map.flyTo(position, 16, {
        animate: true,
        duration: 1.5,
      })
    }
  }, [position, map])

  return null
}

const calculateETA = (currentPos, hospitalPos) => {
  if (!currentPos || !hospitalPos) return null
  const R = 6371
  const lat1 = (currentPos[0] * Math.PI) / 180
  const lat2 = (hospitalPos[0] * Math.PI) / 180
  const dlat = ((hospitalPos[0] - currentPos[0]) * Math.PI) / 180
  const dlng = ((hospitalPos[1] - currentPos[1]) * Math.PI) / 180
  const a =
    Math.sin(dlat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlng / 2) ** 2
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  const distanceKm = R * c
  const etaMinutes = Math.round((distanceKm / 40) * 60)
  return { distanceKm: distanceKm.toFixed(2), etaMinutes }
}

const isOffRoute = (currentPos, routePoints, thresholdKm = 0.05) => {
  if (!routePoints || routePoints.length === 0) return false
  let minDistance = Infinity
  for (const point of routePoints) {
    const R = 6371
    const lat1 = (currentPos[0] * Math.PI) / 180
    const lat2 = (point[0] * Math.PI) / 180
    const dlat = ((point[0] - currentPos[0]) * Math.PI) / 180
    const dlng = ((point[1] - currentPos[1]) * Math.PI) / 180
    const a =
      Math.sin(dlat / 2) ** 2 +
      Math.cos(lat1) * Math.cos(lat2) * Math.sin(dlng / 2) ** 2
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
    const dist = R * c
    if (dist < minDistance) minDistance = dist
  }
  return minDistance > thresholdKm
}

const fetchRoute = async (fromPos, toPos) => {
  const key = import.meta.env.VITE_ORS_API_KEY
  const url = `https://api.openrouteservice.org/v2/directions/driving-car?api_key=${key}&start=${fromPos[1]},${fromPos[0]}&end=${toPos[1]},${toPos[0]}`
  try {
    const res = await fetch(url)
    const json = await res.json()
    const coords = json.features[0].geometry.coordinates
    const points = coords.map(([lng, lat]) => [lat, lng])
    const segments = json.features[0].properties.segments
    const steps = segments?.[0]?.steps || []
    const instructions = steps.map((step) => ({
      instruction: step.instruction,
      distance: step.distance,
      duration: step.duration,
      type: step.type,
    }))
    return { points, instructions }
  } catch (err) {
    console.error('Route fetch failed:', err)
    return { points: null, instructions: [] }
  }
}

const getDirectionIcon = (type) => {
  switch (type) {
    case 0: return '↰'
    case 1: return '↱'
    case 2: return '↑'
    case 3: return '↰'
    case 4: return '↱'
    case 5: return '↰'
    case 6: return '↱'
    case 7: return '↻'
    default: return '↑'
  }
}

export default function MapPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state

  if (!data) return <Navigate to="/dispatch" replace />

  const AMBULANCE_POS = [
    data?.ambulance_lat || 29.8543,
    data?.ambulance_lng || 77.888,
  ]
  const HOSPITAL_POS = [data?.lat, data?.lng]
  const center = [
    (AMBULANCE_POS[0] + HOSPITAL_POS[0]) / 2,
    (AMBULANCE_POS[1] + HOSPITAL_POS[1]) / 2,
  ]

  const [routePoints, setRoutePoints] = useState([])
  const [ambulancePos, setAmbulancePos] = useState(AMBULANCE_POS)
  const [arrived, setArrived] = useState(false)
  const [gpsStatus, setGpsStatus] = useState('Acquiring GPS...')
  const [liveDistance, setLiveDistance] = useState(data.distance_km || null)
  const [liveETA, setLiveETA] = useState(data.eta_minutes || null)
  const [instructions, setInstructions] = useState([])
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [showDirections, setShowDirections] = useState(false)
  const [heading, setHeading] = useState(0)

  const wsRef = useRef(null)
  const isReroutingRef = useRef(false)
  const prevPosRef = useRef(null)

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  // 1. Fetch initial route from ORS on mount
  useEffect(() => {
    fetchRoute(AMBULANCE_POS, HOSPITAL_POS).then(({ points, instructions: instr }) => {
      if (points) setRoutePoints(points)
      if (instr) setInstructions(instr)
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 2. Real GPS tracking with heading calculation
  useEffect(() => {
    if (!navigator.geolocation) {
      setGpsStatus('GPS not available')
      return
    }
    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        const newPos = [position.coords.latitude, position.coords.longitude]

        // Calculate heading from previous position
        if (prevPosRef.current) {
          const prev = prevPosRef.current
          const dLng = ((newPos[1] - prev[1]) * Math.PI) / 180
          const lat1 = (prev[0] * Math.PI) / 180
          const lat2 = (newPos[0] * Math.PI) / 180
          const y = Math.sin(dLng) * Math.cos(lat2)
          const x =
            Math.cos(lat1) * Math.sin(lat2) -
            Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLng)
          const bearing = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360
          setHeading(bearing)
        }

        prevPosRef.current = newPos
        setAmbulancePos(newPos)
        setGpsStatus('Following your live location')
      },
      (error) => {
        console.error('GPS error:', error)
        setGpsStatus('GPS error — using last known position')
      },
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 10000 }
    )
    return () => navigator.geolocation.clearWatch(watchId)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 3. Recalculate distance + ETA + check off-route
  useEffect(() => {
    if (!ambulancePos || !HOSPITAL_POS) return

    const result = calculateETA(ambulancePos, HOSPITAL_POS)
    if (result) {
      setLiveDistance(result.distanceKm)
      setLiveETA(result.etaMinutes)
      if (parseFloat(result.distanceKm) < 0.1) {
        setArrived(true)
        return
      }
    }

    if (
      !isReroutingRef.current &&
      routePoints.length > 0 &&
      isOffRoute(ambulancePos, routePoints)
    ) {
      isReroutingRef.current = true
      setGpsStatus('Re-routing...')

      fetchRoute(ambulancePos, HOSPITAL_POS).then(({ points: newPoints, instructions: newInstr }) => {
        if (newPoints && newPoints.length > 0) {
          setRoutePoints(newPoints)
          setInstructions(newInstr || [])
          setCurrentStepIndex(0)
          setGpsStatus('Following your live location')
        }
        isReroutingRef.current = false
      })
    }
  }, [ambulancePos]) // eslint-disable-line react-hooks/exhaustive-deps

  // 4. WebSocket setup
  useEffect(() => {
    if (!data.case_id) return
    wsRef.current = new WebSocket(
      `ws://localhost:8000/ws/ambulance/${data.case_id}`
    )
    wsRef.current.onopen = () => console.log('WebSocket connected')
    wsRef.current.onerror = (err) => console.error('WebSocket error:', err)
    return () => wsRef.current?.close()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // 5. Send GPS position via WebSocket
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({
          lat: ambulancePos[0],
          lng: ambulancePos[1],
          eta_minutes: liveETA || 0,
        })
      )
    }
  }, [ambulancePos, liveETA])

  useEffect(() => {
    if (arrived && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ lat: ambulancePos[0], lng: ambulancePos[1], eta_minutes: 0 })
      )
    }
  }, [arrived]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <style>{`
        @keyframes live-dot-pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.6); opacity: 0.4; }
        }
        .animate-live-dot { animation: live-dot-pulse 1.5s ease-in-out infinite; }
        .leaflet-container { height: 100%; width: 100%; }
      `}</style>

      <div className="flex flex-col h-screen overflow-hidden" style={{ backgroundColor: '#0A1628' }}>
        {/* HEADER */}
        <header className="flex-shrink-0 shadow-lg z-[2000]" style={{ backgroundColor: '#0A1628', height: '56px' }}>
          <div className="max-w-5xl mx-auto px-4 h-full flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button onClick={() => navigate(-1)} className="text-gray-400 hover:text-white transition mr-1">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#16A34A' }}>
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <span className="text-lg font-bold text-white">MediRoute</span>
            </div>
            <div className="flex items-center gap-3">
              <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-white font-medium transition px-3 py-1.5 rounded-lg hover:bg-white/10">
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* STATUS BAR */}
        <div
          className="flex-shrink-0 flex items-center justify-between px-6 py-2 z-[1999]"
          style={{ backgroundColor: '#0F2238', height: '48px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}
        >
          <div className="flex items-center gap-2">
            <span className="relative flex h-2 w-2">
              {!arrived && (
                <span className="absolute inline-flex h-full w-full rounded-full animate-live-dot" style={{ backgroundColor: gpsStatus === 'Re-routing...' ? '#F59E0B' : '#4ADE80' }}></span>
              )}
              <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: arrived ? '#16A34A' : gpsStatus === 'Re-routing...' ? '#F59E0B' : '#4ADE80' }}></span>
            </span>
            <span className="text-sm font-medium" style={{ color: arrived ? '#4ADE80' : gpsStatus === 'Re-routing...' ? '#F59E0B' : '#9CA3AF' }}>
              {arrived ? 'ARRIVED' : `Distance: ${liveDistance ?? '--'} km | ETA: ${liveETA ?? '--'} min`}
            </span>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {arrived ? (
              <span className="font-semibold" style={{ color: '#4ADE80' }}>Arrived</span>
            ) : (
              <span className="font-mono font-semibold text-white">{liveETA ?? '--'} min</span>
            )}
          </div>
        </div>

        {/* MAP */}
        <div className="relative flex-1" style={{ height: 'calc(100vh - 104px)' }}>
          <MapContainer center={center} zoom={16} zoomControl={false} style={{ width: '100%', height: '100%' }}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/">CARTO</a>'
              url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
            />
            <ZoomControl position="bottomright" />
            <FlyToLocation position={ambulancePos} heading={heading} />
            <Marker position={ambulancePos} icon={ambulanceIcon}>
              <Popup>🚑 Ambulance — Live GPS</Popup>
            </Marker>
            <Marker position={HOSPITAL_POS} icon={hospitalIcon}>
              <Popup>{data?.hospital_name}</Popup>
            </Marker>
            {routePoints.length > 0 && (
              <Polyline
                positions={routePoints}
                pathOptions={{
                  color: '#3B82F6',
                  weight: 6,
                  opacity: 0.9,
                  lineCap: 'round',
                  lineJoin: 'round',
                }}
              />
            )}
          </MapContainer>

          {/* NEXT TURN BANNER */}
          {instructions.length > 0 && !arrived && (
            <div className="absolute bottom-[220px] left-1/2 -translate-x-1/2 z-[1001] w-[380px]">
              <div
                className="rounded-xl px-4 py-3 flex items-center gap-3 shadow-xl border border-white/10"
                style={{ backgroundColor: 'rgba(10,22,40,0.95)' }}
              >
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-xl text-white flex-shrink-0"
                  style={{ backgroundColor: '#2563EB' }}
                >
                  {getDirectionIcon(instructions[currentStepIndex]?.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-semibold text-sm truncate">
                    {instructions[currentStepIndex]?.instruction || 'Follow the route'}
                  </p>
                  <p className="text-gray-400 text-xs mt-0.5">
                    {instructions[currentStepIndex]?.distance
                      ? `${(instructions[currentStepIndex].distance / 1000).toFixed(1)} km`
                      : ''}
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* FLOATING INFO BOX */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] w-[380px] pointer-events-auto">
            <div
              className="rounded-xl shadow-2xl p-5 border border-white/10"
              style={{ backgroundColor: 'rgba(10,22,40,0.92)', backdropFilter: 'blur(8px)' }}
            >
              {arrived && (
                <div
                  className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold mb-3"
                  style={{ backgroundColor: 'rgba(22,163,74,0.2)', color: '#4ADE80' }}
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  ARRIVED
                </div>
              )}

              <h3 className="text-lg font-bold text-white mb-3">{data.hospital_name}</h3>

              <div className="flex items-center gap-6 mb-4">
                <div className="flex items-center gap-1.5">
                  <svg className="w-4 h-4" style={{ color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="text-sm text-gray-400">
                    <span className="font-semibold text-white font-mono">{liveDistance ?? '--'}</span> km
                  </span>
                </div>
                <div className="flex items-center gap-1.5">
                  <svg className="w-4 h-4" style={{ color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <span className="text-sm text-gray-400">
                    {arrived ? (
                      <span className="font-semibold" style={{ color: '#4ADE80' }}>Arrived</span>
                    ) : (
                      <>
                        <span className="font-semibold text-white font-mono">{liveETA ?? '--'}</span> min ETA
                      </>
                    )}
                  </span>
                </div>
                {!arrived && (
                  <div className="flex items-center gap-1 ml-auto">
                    <span className="relative flex h-2 w-2">
                      <span className="absolute inline-flex h-full w-full rounded-full animate-live-dot" style={{ backgroundColor: '#4ADE80' }}></span>
                      <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: '#16A34A' }}></span>
                    </span>
                    <span className="text-xs font-bold" style={{ color: '#4ADE80' }}>GPS</span>
                  </div>
                )}
              </div>

              {/* GPS status pill */}
              {!arrived && (
                <div
                  className="flex items-center gap-2 mb-3 px-3 py-2 rounded-lg"
                  style={{ backgroundColor: gpsStatus === 'Re-routing...' ? 'rgba(245,158,11,0.1)' : 'rgba(22,163,74,0.1)' }}
                >
                  <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full rounded-full animate-live-dot" style={{ backgroundColor: gpsStatus === 'Re-routing...' ? '#F59E0B' : '#4ADE80' }}></span>
                    <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: gpsStatus === 'Re-routing...' ? '#F59E0B' : '#16A34A' }}></span>
                  </span>
                  <span className="text-xs font-medium" style={{ color: gpsStatus === 'Re-routing...' ? '#F59E0B' : '#4ADE80' }}>
                    {gpsStatus}
                  </span>
                </div>
              )}

              {/* Directions toggle */}
              {instructions.length > 0 && !arrived && (
                <>
                  <button
                    onClick={() => setShowDirections(!showDirections)}
                    className="w-full py-2 text-xs font-semibold rounded-lg border mb-3 transition hover:bg-white/5"
                    style={{ borderColor: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.7)' }}
                  >
                    {showDirections ? '▲ Hide Directions' : '▼ Show All Directions'}
                  </button>

                  {showDirections && (
                    <div className="mb-3 max-h-48 overflow-y-auto space-y-1">
                      {instructions.map((step, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-2 px-2 py-1.5 rounded-lg text-xs"
                          style={{
                            backgroundColor: idx === currentStepIndex ? 'rgba(37,99,235,0.2)' : 'transparent',
                            color: idx === currentStepIndex ? 'white' : 'rgba(255,255,255,0.5)',
                          }}
                        >
                          <span className="flex-shrink-0 w-5 text-center">
                            {getDirectionIcon(step.type)}
                          </span>
                          <span className="flex-1">{step.instruction}</span>
                          <span className="flex-shrink-0 text-gray-500">
                            {(step.distance / 1000).toFixed(1)}km
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* Mark as Arrived / Back to Result */}
              {!arrived ? (
                <button
                  onClick={() => setArrived(true)}
                  className="w-full py-2.5 font-bold rounded-lg text-sm text-white transition hover:opacity-90"
                  style={{ backgroundColor: '#16A34A' }}
                >
                  ✓ Mark as Arrived
                </button>
              ) : (
                <button
                  onClick={() => navigate(-1)}
                  className="w-full py-2 font-semibold rounded-lg text-sm border transition hover:bg-white/10"
                  style={{ borderColor: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.8)' }}
                >
                  Back to Result
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
