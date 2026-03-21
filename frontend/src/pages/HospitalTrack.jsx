import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { LoadScript, GoogleMap, Marker } from '@react-google-maps/api'
import api from '../api/axios'

const mapContainerStyle = {
  width: '100%',
  height: '55vh',
}

const HOSPITAL_POS = { lat: 29.8700, lng: 77.8960 }

export default function HospitalTrack() {
  const { case_id } = useParams()
  const navigate = useNavigate()

  const [caseData, setCaseData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ambulancePos, setAmbulancePos] = useState(null)
  const [etaCountdown, setEtaCountdown] = useState(0)
  const [arrived, setArrived] = useState(false)

  const wsRef = useRef(null)

  useEffect(() => {
    const fetchCase = async () => {
      try {
        const res = await api.get('/api/cases/')
        const currentCase = res.data.find((c) => c.id === parseInt(case_id))
        if (currentCase) {
          setCaseData(currentCase)
          setAmbulancePos({
            lat: currentCase.ambulance_lat,
            lng: currentCase.ambulance_lng,
          })
          setEtaCountdown(currentCase.eta_minutes * 60)
        }
      } catch (err) {
        console.error('Error fetching case:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchCase()
  }, [case_id])

  useEffect(() => {
    if (!case_id) return

    wsRef.current = new WebSocket(`ws://localhost:8000/ws/hospital/${case_id}`)
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data)
      setAmbulancePos({ lat: data.lat, lng: data.lng })
      setEtaCountdown(data.eta_minutes * 60)
      if (data.eta_minutes === 0) setArrived(true)
    }

    wsRef.current.onerror = (err) => {
        console.error('WebSocket error:', err)
    }

    return () => wsRef.current?.close()
  }, [case_id])

  useEffect(() => {
    if (arrived || etaCountdown <= 0) return
    const timer = setInterval(() => {
      setEtaCountdown(prev => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [arrived, etaCountdown])

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const formatCountdown = (totalSec) => {
    if (totalSec <= 0) return '0:00'
    const m = Math.floor(totalSec / 60)
    const s = totalSec % 60
    return `${m}:${s.toString().padStart(2, '0')}`
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0F1B2D] flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-[#16A34A] border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  if (!caseData) {
    return (
      <div className="min-h-screen bg-[#0F1B2D] flex items-center justify-center text-white text-xl">
        Case not found
      </div>
    )
  }

  const center = ambulancePos ? {
    lat: (ambulancePos.lat + HOSPITAL_POS.lat) / 2,
    lng: (ambulancePos.lng + HOSPITAL_POS.lng) / 2,
  } : HOSPITAL_POS

  return (
    <>
      <style>{`
        @keyframes pulse-red {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.1); }
        }
        .animate-pulse-red {
          animation: pulse-red 1.5s infinite;
        }
      `}</style>
      <div className="min-h-screen flex flex-col bg-[#0F1B2D] text-white">
        {/* HEADER */}
        <header className="px-6 py-4 flex items-center justify-between" style={{ backgroundColor: '#0A1628' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#16A34A' }}>
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold">MediRoute</h1>
              <p className="text-xs text-gray-400">Hospital Dashboard</p>
            </div>
            {!arrived && (
              <span className="ml-4 px-3 py-1 bg-red-600 text-white text-xs font-bold rounded-full animate-pulse-red">
                INCOMING
              </span>
            )}
          </div>
          <button onClick={handleLogout} className="text-gray-400 hover:text-white transition">
            Logout
          </button>
        </header>

        {/* ALERT BAR */}
        <div className={`px-6 py-3 flex items-center justify-between shadow-lg ${arrived ? 'bg-[#16A34A]' : 'bg-gradient-to-r from-red-600 to-orange-500'}`}>
          <div className="flex items-center gap-2 font-bold text-lg">
            {arrived ? '✓ Ambulance Has Arrived' : '🚨 INCOMING EMERGENCY — Prepare Immediately'}
          </div>
          <div className="font-mono font-bold bg-black/20 px-3 py-1 rounded">
            Case #{case_id}
          </div>
        </div>

        {/* MAP SECTION */}
        <div style={{ height: '55vh' }} className="w-full relative">
          <LoadScript googleMapsApiKey={import.meta.env.VITE_GOOGLE_MAPS_KEY}>
            <GoogleMap
              mapContainerStyle={mapContainerStyle}
              center={center}
              zoom={13}
              options={{ disableDefaultUI: true, zoomControl: true }}
            >
              <Marker
                position={HOSPITAL_POS}
                label={{ text: 'H', color: 'white', fontWeight: 'bold' }}
                icon={{
                  path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z',
                  fillColor: '#16A34A',
                  fillOpacity: 1,
                  strokeColor: '#15803D',
                  strokeWeight: 1,
                  scale: 2,
                  anchor: { x: 12, y: 24 },
                  labelOrigin: { x: 12, y: 10 },
                }}
              />
              {ambulancePos && (
                <Marker
                  position={ambulancePos}
                  label={{ text: '🚑', fontSize: '24px' }}
                  icon={{ path: 'M0 0', scale: 0 }}
                  zIndex={100}
                />
              )}
            </GoogleMap>
          </LoadScript>
        </div>

        {/* INFO PANEL */}
        <div className="flex-1 p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Column 1 - Patient Info */}
          <div className="rounded-xl p-5 shadow-xl flex flex-col" style={{ backgroundColor: '#0A1628' }}>
            <h3 className="text-gray-400 text-sm font-bold uppercase tracking-wider mb-2">Patient Details</h3>
            <p className="text-3xl font-extrabold text-red-500 mb-4 capitalize">{caseData.condition}</p>
            <div className="text-sm font-medium text-gray-400 mb-2">Equipment Required:</div>
            <div className="flex flex-wrap gap-2">
              {caseData.equipment_needed?.length > 0 ? (
                caseData.equipment_needed.map((eq) => (
                  <span key={eq} className="px-3 py-1 bg-[#16A34A] bg-opacity-20 text-[#4ADE80] text-xs font-bold rounded-md uppercase">
                    {eq.replace('_', ' ')}
                  </span>
                ))
              ) : (
                <span className="text-gray-500">None</span>
              )}
            </div>
          </div>

          {/* Column 2 - Live Stats */}
          <div className="rounded-xl p-5 shadow-xl flex flex-col justify-center items-center text-center" style={{ backgroundColor: '#0A1628' }}>
            <h3 className="text-gray-400 text-sm font-bold uppercase tracking-wider mb-2 self-start w-full">Live Status</h3>
            <div className={`text-5xl font-mono font-bold mb-2 ${arrived ? 'text-[#4ADE80]' : 'text-[#4ADE80]'}`}>
              {arrived ? 'ARRIVED' : formatCountdown(etaCountdown)}
            </div>
            {!arrived && (
              <div className="text-gray-400 font-medium mb-3">{caseData.distance_km} km</div>
            )}
            <div className="flex items-center gap-2 mt-auto">
              {!arrived ? (
                <>
                  <span className="w-3 h-3 bg-[#4ADE80] rounded-full animate-pulse-red"></span>
                  <span className="font-bold text-[#4ADE80]">En Route</span>
                </>
              ) : (
                <>
                  <svg className="w-5 h-5 text-[#4ADE80]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                  <span className="font-bold text-[#4ADE80]">ARRIVED</span>
                </>
              )}
            </div>
          </div>

          {/* Column 3 - Actions */}
          <div className="rounded-xl p-5 shadow-xl flex flex-col" style={{ backgroundColor: '#0A1628' }}>
            <h3 className="text-gray-400 text-sm font-bold uppercase tracking-wider mb-4">Actions</h3>
            <button
              onClick={() => alert('Marked as ready — team notified')}
              className="w-full py-3 mb-3 bg-[#16A34A] hover:bg-[#15803D] text-white font-bold rounded-lg transition"
            >
              ✓ Mark as Ready
            </button>
            <button
              onClick={() => alert('Calling ambulance crew...')}
              className="w-full py-3 mb-auto border-2 border-blue-500 hover:bg-blue-500/10 text-blue-400 font-bold rounded-lg transition"
            >
              Call Ambulance
            </button>
            <div className="text-center text-xs text-gray-500 mt-4">
              {arrived ? 'Patient has arrived.' : `Patient arriving in ${formatCountdown(etaCountdown)}`}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
