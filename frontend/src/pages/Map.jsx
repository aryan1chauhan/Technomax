import { useState, useCallback } from 'react'
import { useLocation, useNavigate, Navigate } from 'react-router-dom'
import {
  LoadScript,
  GoogleMap,
  Marker,
  DirectionsService,
  DirectionsRenderer,
} from '@react-google-maps/api'

const AMBULANCE_POS = { lat: 29.8543, lng: 77.8880 }

const mapContainerStyle = {
  width: '100%',
  height: '100%',
}

export default function MapPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state
  console.log('Maps Key:', import.meta.env.VITE_GOOGLE_MAPS_KEY)

  const [directions, setDirections] = useState(null)
  const [requestSent, setRequestSent] = useState(false)

  if (!data) {
    return <Navigate to="/dispatch" replace />
  }

  const hospitalPos = { lat: data.lat, lng: data.lng }

  const center = {
    lat: (AMBULANCE_POS.lat + hospitalPos.lat) / 2,
    lng: (AMBULANCE_POS.lng + hospitalPos.lng) / 2,
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const directionsCallback = useCallback(
    (result, status) => {
      if (status === 'OK' && !directions) {
        setDirections(result)
      }
    },
    [directions]
  )

  return (
    <div className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm z-10">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-600 rounded-lg flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <span className="text-lg font-bold text-gray-900">MediRoute</span>
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-red-600 font-medium transition"
          >
            Logout
          </button>
        </div>
      </header>

      {/* Map */}
      <div className="flex-1 relative">
        <LoadScript googleMapsApiKey={import.meta.env.VITE_GOOGLE_MAPS_KEY}>
          <GoogleMap
            mapContainerStyle={mapContainerStyle}
            center={center}
            zoom={13}
          >
            {/* Ambulance Marker */}
            <Marker
              position={AMBULANCE_POS}
              label={{ text: 'A', color: 'white', fontWeight: 'bold' }}
              icon={{
                path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z',
                fillColor: '#DC2626',
                fillOpacity: 1,
                strokeColor: '#991B1B',
                strokeWeight: 1,
                scale: 2,
                anchor: { x: 12, y: 24 },
                labelOrigin: { x: 12, y: 10 },
              }}
            />

            {/* Hospital Marker */}
            <Marker
              position={hospitalPos}
              label={{ text: 'H', color: 'white', fontWeight: 'bold' }}
              icon={{
                path: 'M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z',
                fillColor: '#2563EB',
                fillOpacity: 1,
                strokeColor: '#1E40AF',
                strokeWeight: 1,
                scale: 2,
                anchor: { x: 12, y: 24 },
                labelOrigin: { x: 12, y: 10 },
              }}
            />

            {/* Directions Service — fire only once */}
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

            {/* Directions Renderer */}
            {directions && (
              <DirectionsRenderer
                options={{
                  directions,
                  suppressMarkers: true,
                  polylineOptions: {
                    strokeColor: '#2563EB',
                    strokeWeight: 5,
                    strokeOpacity: 0.8,
                  },
                }}
              />
            )}
          </GoogleMap>
        </LoadScript>

        {/* Info Box */}
        <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 z-10 min-w-[320px]">
          <div className="bg-white rounded-xl shadow-lg p-5">
            <h3 className="text-lg font-bold text-gray-900 mb-2">{data.hospital_name}</h3>
            <div className="flex items-center gap-4 mb-4">
              <div className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <span className="text-sm text-gray-600">
                  <span className="font-semibold text-gray-900">{data.distance_km}</span> km
                </span>
              </div>
              <div className="flex items-center gap-1.5">
                <svg className="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span className="text-sm text-gray-600">
                  <span className="font-semibold text-gray-900">{data.eta_minutes}</span> min
                </span>
              </div>
            </div>
            <button
              onClick={() => navigate(-1)}
              className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition text-sm border border-gray-200"
            >
              Back to Result
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
