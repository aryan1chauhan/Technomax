import { useState, useCallback, useEffect, useRef } from 'react'
import { useLocation, useNavigate, Navigate } from 'react-router-dom'
import {
  LoadScript,
  GoogleMap,
  Marker,
  DirectionsService,
  DirectionsRenderer,
  Polyline,
} from '@react-google-maps/api'

const AMBULANCE_POS = { lat: 29.8543, lng: 77.8880 }
const LIBRARIES = ['places', 'geometry']

const mapContainerStyle = {
  width: '100%',
  height: '100%',
}

const ambulanceSVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="24" fill="#EF4444"/>
  <text x="24" y="32" text-anchor="middle" font-size="24">🚑</text>
</svg>`

const hospitalSVG = `
<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="8" fill="#16A34A"/>
  <text x="24" y="32" text-anchor="middle" font-size="24">🏥</text>
</svg>`

export default function MapPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state
  const case_id = data?.case_id

  const [directions, setDirections] = useState(null)
  const [requestSent, setRequestSent] = useState(false)

  // Simulation states
  const [routeSteps, setRouteSteps] = useState([])
  const [animatedPath, setAnimatedPath] = useState([])
  const [routeDrawn, setRouteDrawn] = useState(false)
  const [ambulancePos, setAmbulancePos] = useState(AMBULANCE_POS)
  const [arrived, setArrived] = useState(false)
  const [etaCountdown, setEtaCountdown] = useState(null)
  const [simStatus, setSimStatus] = useState('Calculating Route...')

  const ambulanceMoveRef = useRef(null)
  const etaIntervalRef = useRef(null)
  const wsRef = useRef(null)
  const mapRef = useRef(null)
  const animationRef = useRef(null)
  const etaRef = useRef(data?.eta_minutes ? data.eta_minutes * 60 : 0)

  if (!data) {
    return <Navigate to="/dispatch" replace />
  }

  const hospitalPos = { lat: data.lat, lng: data.lng }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const onMapLoad = (map) => {
    mapRef.current = map
    map.setTilt(60)
    map.setHeading(0)
    map.setZoom(17)
    map.setCenter(AMBULANCE_POS)
    map.setMapTypeId('roadmap')
  }

  const directionsCallback = useCallback(
    (result, status) => {
      if (status === 'OK' && !directions) {
        setDirections(result)

        const route = result.routes[0]
        const allPoints = []
        route.legs[0].steps.forEach((step) => {
          step.path.forEach((point) => {
            allPoints.push({ lat: point.lat(), lng: point.lng() })
          })
        })
        setRouteSteps(allPoints)
        setSimStatus(`En Route → ${data.hospital_name}`)
      }
    },
    [directions, data?.hospital_name]
  )

  // --- Phase 1: Animate route drawing ---
  useEffect(() => {
    if (routeSteps.length === 0 || routeDrawn) return

    let idx = 0
    const totalDuration = 2000
    const interval = Math.max(totalDuration / routeSteps.length, 5)

    const timer = setInterval(() => {
      idx++
      if (idx >= routeSteps.length) {
        setAnimatedPath([...routeSteps])
        setRouteDrawn(true)
        clearInterval(timer)
      } else {
        setAnimatedPath(routeSteps.slice(0, idx + 1))
      }
    }, interval)

    return () => clearInterval(timer)
  }, [routeSteps, routeDrawn])

  // --- Phase 2: Smooth ambulance movement with requestAnimationFrame ---
  useEffect(() => {
    if (!routeDrawn || arrived || routeSteps.length === 0) return

    // Open WebSocket
    if (case_id && !wsRef.current) {
      wsRef.current = new WebSocket(`ws://localhost:8000/ws/ambulance/${case_id}`)
      wsRef.current.onopen = () => {
        console.log('WebSocket connected — ambulance tracking active')
      }
      wsRef.current.onerror = (err) => {
        console.error('WebSocket error:', err)
      }
    }

    const totalDuration = 20000 // 20 seconds
    const startTime = performance.now()

    const animate = (now) => {
      const elapsed = now - startTime
      const progress = Math.min(elapsed / totalDuration, 1)

      // Find which segment we're on
      const totalSegments = routeSteps.length - 1
      const exactIdx = progress * totalSegments
      const segIdx = Math.min(Math.floor(exactIdx), totalSegments - 1)
      const segProgress = exactIdx - segIdx

      const prev = routeSteps[segIdx]
      const next = routeSteps[Math.min(segIdx + 1, totalSegments)]

      // Interpolate smooth position
      const currentPosition = {
        lat: prev.lat + (next.lat - prev.lat) * segProgress,
        lng: prev.lng + (next.lng - prev.lng) * segProgress,
      }

      setAmbulancePos(currentPosition)

      // Camera tracking — pan map and rotate heading
      if (mapRef.current && window.google) {
        mapRef.current.panTo(currentPosition)
        try {
          const prevLatLng = new window.google.maps.LatLng(prev.lat, prev.lng)
          const nextLatLng = new window.google.maps.LatLng(next.lat, next.lng)
          const heading = window.google.maps.geometry.spherical.computeHeading(prevLatLng, nextLatLng)
          mapRef.current.setHeading(heading)
        } catch (e) {
          // geometry lib may not be ready
        }
      }

      // Send WebSocket update
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          lat: currentPosition.lat,
          lng: currentPosition.lng,
          eta_minutes: Math.ceil((etaRef.current || 0) / 60)
        }))
      }

      if (progress >= 1) {
        // Arrived
        setAmbulancePos(routeSteps[totalSegments])
        setArrived(true)
        setSimStatus('ARRIVED')
        // Final WS message
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({
            lat: routeSteps[totalSegments].lat,
            lng: routeSteps[totalSegments].lng,
            eta_minutes: 0
          }))
        }
        return
      }

      animationRef.current = requestAnimationFrame(animate)
    }

    animationRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
    }
  }, [routeDrawn, arrived, routeSteps, case_id])

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close()
      if (animationRef.current) cancelAnimationFrame(animationRef.current)
    }
  }, [])

  // --- ETA Countdown ---
  useEffect(() => {
    if (!routeDrawn || arrived) return

    const startEta = data.eta_minutes
    setEtaCountdown(startEta * 60)
    etaRef.current = startEta * 60

    etaIntervalRef.current = setInterval(() => {
      setEtaCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(etaIntervalRef.current)
          etaRef.current = 0
          return 0
        }
        etaRef.current = prev - 1
        return prev - 1
      })
    }, 1000)

    return () => {
      if (etaIntervalRef.current) clearInterval(etaIntervalRef.current)
    }
  }, [routeDrawn, arrived, data.eta_minutes])

  // Stop countdown when arrived
  useEffect(() => {
    if (arrived && etaIntervalRef.current) {
      clearInterval(etaIntervalRef.current)
      setEtaCountdown(0)
    }
  }, [arrived])

  const formatCountdown = (totalSec) => {
    if (totalSec === null) return '--:--'
    if (totalSec <= 0) return '0:00'
    const m = Math.floor(totalSec / 60)
    const s = totalSec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  const ambulanceIcon = typeof window !== 'undefined' && window.google ? {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(ambulanceSVG),
    scaledSize: new window.google.maps.Size(48, 48),
    anchor: new window.google.maps.Point(24, 24),
  } : undefined

  const hospitalIcon = typeof window !== 'undefined' && window.google ? {
    url: 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(hospitalSVG),
    scaledSize: new window.google.maps.Size(48, 48),
    anchor: new window.google.maps.Point(24, 48),
  } : undefined

  return (
    <>
      <style>{`
        @keyframes live-dot-pulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.6); opacity: 0.4; }
        }
        .animate-live-dot {
          animation: live-dot-pulse 1.5s ease-in-out infinite;
        }
        @keyframes arrived-pop {
          0% { transform: translate(-50%, -50%) scale(0); opacity: 0; }
          60% { transform: translate(-50%, -50%) scale(1.1); opacity: 1; }
          100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
        }
        .animate-arrived-pop {
          animation: arrived-pop 0.6s ease-out forwards;
        }
      `}</style>

      <div className="h-screen flex flex-col">
        {/* Header */}
        <header className="z-10 shadow-lg" style={{ backgroundColor: '#0A1628' }}>
          <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate(-1)}
                className="text-gray-400 hover:text-white transition mr-2"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                </svg>
              </button>
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#16A34A' }}>
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <div>
                <span className="text-lg font-bold text-white">MediRoute</span>
                <p className="text-xs text-gray-400 -mt-0.5">Live Dispatch</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="relative flex h-2.5 w-2.5">
                <span className="absolute inline-flex h-full w-full rounded-full animate-live-dot" style={{ backgroundColor: arrived ? '#4ADE80' : '#16A34A' }}></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5" style={{ backgroundColor: '#16A34A' }}></span>
              </span>
              <span className="text-sm font-mono text-gray-300">
                {arrived ? (
                  <span style={{ color: '#4ADE80' }}>Arrived</span>
                ) : (
                  `ETA ${formatCountdown(etaCountdown)}`
                )}
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-400 hover:text-white font-medium transition px-3 py-1.5 rounded-lg hover:bg-white/10 ml-2"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* Map */}
        <div className="flex-1 relative">
          <LoadScript googleMapsApiKey={import.meta.env.VITE_GOOGLE_MAPS_KEY} libraries={LIBRARIES}>
            <GoogleMap
              mapContainerStyle={mapContainerStyle}
              center={AMBULANCE_POS}
              zoom={17}
              onLoad={onMapLoad}
              options={{
                mapTypeId: 'roadmap',
                tilt: 60,
                heading: 0,
                rotateControl: true,
                streetViewControl: false,
                fullscreenControl: false,
                mapTypeControl: false,
              }}
            >
              {/* Route Polyline */}
              {animatedPath.length > 1 && (
                <Polyline
                  path={animatedPath}
                  options={{
                    strokeColor: '#3B82F6',
                    strokeWeight: 6,
                    strokeOpacity: 0.8,
                  }}
                />
              )}

              {/* Moving Ambulance Marker */}
              <Marker
                position={ambulancePos}
                icon={ambulanceIcon}
                zIndex={1000}
              />

              {/* Hospital Marker */}
              <Marker
                position={hospitalPos}
                icon={hospitalIcon}
                zIndex={999}
              />

              {/* Directions Service — fire once */}
              {!requestSent && (
                <DirectionsService
                  options={{
                    destination: hospitalPos,
                    origin: AMBULANCE_POS,
                    travelMode: 'DRIVING',
                  }}
                  callback={(result, status) => {
                    setRequestSent(true)
                    directionsCallback(result, status)
                  }}
                />
              )}

              {/* Hidden DirectionsRenderer */}
              {directions && (
                <DirectionsRenderer
                  options={{
                    directions,
                    suppressMarkers: true,
                    polylineOptions: { strokeOpacity: 0 },
                  }}
                />
              )}
            </GoogleMap>
          </LoadScript>

          {/* Arrived Overlay */}
          {arrived && (
            <div className="absolute inset-0 flex items-center justify-center z-20 pointer-events-none">
              <div className="animate-arrived-pop px-8 py-4 rounded-2xl shadow-2xl" style={{ backgroundColor: 'rgba(22,163,74,0.95)' }}>
                <div className="flex items-center gap-3">
                  <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="text-3xl font-extrabold text-white tracking-wide">ARRIVED</span>
                </div>
              </div>
            </div>
          )}

          {/* Info Panel — floating at bottom center */}
          <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 z-10 w-[380px]">
            <div className="rounded-xl shadow-2xl p-5 backdrop-blur-sm" style={{ backgroundColor: 'rgba(10,22,40,0.92)' }}>
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

              <div className="flex items-center gap-5 mb-4">
                <div className="flex items-center gap-1.5">
                  <svg className="w-4 h-4" style={{ color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <span className="text-sm text-gray-400">
                    <span className="font-semibold text-white">{data.distance_km}</span> km
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
                        <span className="font-semibold text-white font-mono">{formatCountdown(etaCountdown)}</span> ETA
                      </>
                    )}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 ml-auto">
                  {!arrived && (
                    <>
                      <span className="relative flex h-2 w-2">
                        <span className="absolute inline-flex h-full w-full rounded-full animate-live-dot" style={{ backgroundColor: '#4ADE80' }}></span>
                        <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: '#16A34A' }}></span>
                      </span>
                      <span className="text-xs font-bold text-[#4ADE80]">LIVE</span>
                    </>
                  )}
                </div>
              </div>

              <button
                onClick={() => navigate(-1)}
                className="w-full py-2 font-semibold rounded-lg transition text-sm border"
                style={{ borderColor: 'rgba(255,255,255,0.15)', color: 'rgba(255,255,255,0.7)' }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.08)'
                  e.currentTarget.style.color = '#fff'
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'transparent'
                  e.currentTarget.style.color = 'rgba(255,255,255,0.7)'
                }}
              >
                Back to Result
              </button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
