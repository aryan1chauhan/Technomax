import { useLocation, useNavigate, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'

export default function Result() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state
  const [animatedWidth, setAnimatedWidth] = useState(0)

  if (!data) {
    return <Navigate to="/dispatch" replace />
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const scorePercent = Math.round(data.final_score * 100)

  // Trigger score bar animation on mount
  useEffect(() => {
    const timer = setTimeout(() => setAnimatedWidth(scorePercent), 100)
    return () => clearTimeout(timer)
  }, [scorePercent])

  const scoreColor =
    scorePercent > 70 ? '#16A34A' : scorePercent >= 50 ? '#F59E0B' : '#EF4444'

  return (
    <>
      <style>{`
        @keyframes live-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .animate-live-pulse {
          animation: live-pulse 1.5s ease-in-out infinite;
        }
      `}</style>

      <div className="min-h-screen" style={{ backgroundColor: '#0F1B2D' }}>
        {/* Header Bar */}
        <header style={{ backgroundColor: '#0A1628' }} className="shadow-lg">
          <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#16A34A' }}>
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
                </svg>
              </div>
              <div>
                <span className="text-lg font-bold text-white">MediRoute</span>
                <p className="text-xs text-gray-400 -mt-0.5">Emergency Dispatch</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              {/* LIVE Badge */}
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-bold text-white animate-live-pulse" style={{ backgroundColor: '#DC2626' }}>
                <span className="w-1.5 h-1.5 bg-white rounded-full"></span>
                LIVE
              </span>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-400 hover:text-white font-medium transition px-3 py-1.5 rounded-lg hover:bg-white/10"
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="max-w-[680px] mx-auto px-4 py-10">
          <div className="bg-white rounded-2xl shadow-xl overflow-hidden">
            {/* Green urgency strip */}
            <div className="h-2" style={{ backgroundColor: '#16A34A' }}></div>

            <div className="p-8">
              {/* Hospital Section */}
              <div className="flex items-center gap-3 mb-2">
                <div className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0" style={{ backgroundColor: '#DCFCE7' }}>
                  <svg className="w-5 h-5" style={{ color: '#16A34A' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <span className="text-xs font-bold tracking-wider uppercase" style={{ color: '#16A34A' }}>
                  BEST MATCH FOUND
                </span>
              </div>
              <h2 className="text-2xl font-bold mb-1" style={{ color: '#0A1628' }}>{data.hospital_name}</h2>
              <p className="text-sm text-gray-500 mb-8">{data.address}</p>

              {/* Score Bar */}
              <div className="mb-8">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-600">Compatibility Score</span>
                  <span className="text-sm font-bold" style={{ color: scoreColor }}>{scorePercent}%</span>
                </div>
                <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${animatedWidth}%`,
                      backgroundColor: scoreColor,
                      transition: 'width 1.5s ease-out',
                    }}
                  ></div>
                </div>
              </div>

              {/* Stats Row */}
              <div className="grid grid-cols-3 gap-3 mb-8">
                <div className="rounded-xl p-4 text-center" style={{ backgroundColor: '#0A1628' }}>
                  <svg className="w-5 h-5 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-xl font-bold text-white">{data.eta_minutes} min</p>
                  <p className="text-xs text-gray-400 mt-0.5">ETA</p>
                </div>
                <div className="rounded-xl p-4 text-center" style={{ backgroundColor: '#0A1628' }}>
                  <svg className="w-5 h-5 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                  <p className="text-xl font-bold text-white">{data.distance_km} km</p>
                  <p className="text-xs text-gray-400 mt-0.5">Distance</p>
                </div>
                <div className="rounded-xl p-4 text-center" style={{ backgroundColor: '#0A1628' }}>
                  <svg className="w-5 h-5 text-gray-400 mx-auto mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                  </svg>
                  <p className="text-xl font-bold text-white">{data.beds_available}</p>
                  <p className="text-xs text-gray-400 mt-0.5">Beds Available</p>
                </div>
              </div>

              {/* Equipment Section */}
              <div className="mb-8">
                <h3 className="text-sm font-semibold mb-3" style={{ color: '#0A1628' }}>Equipment Status</h3>

                {/* Matched Equipment */}
                <div className="flex flex-wrap gap-2 mb-3">
                  {data.equipment_matched && data.equipment_matched.length > 0 ? (
                    data.equipment_matched.map((item) => (
                      <span
                        key={item}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-full uppercase"
                        style={{ backgroundColor: '#DCFCE7', color: '#15803D' }}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                        </svg>
                        {item.replace('_', ' ')}
                      </span>
                    ))
                  ) : (
                    <span className="text-sm text-gray-400">None requested</span>
                  )}
                </div>

                {/* Missing Equipment */}
                <div className="flex flex-wrap gap-2">
                  {data.equipment_missing && data.equipment_missing.length > 0 ? (
                    data.equipment_missing.map((item) => (
                      <span
                        key={item}
                        className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-full uppercase"
                        style={{ backgroundColor: '#FEE2E2', color: '#DC2626' }}
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                        {item.replace('_', ' ')}
                      </span>
                    ))
                  ) : (
                    <span className="inline-flex items-center gap-1 text-sm font-medium" style={{ color: '#16A34A' }}>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      All equipment available
                    </span>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() =>
                    navigate('/map', {
                      state: {
                        ...location.state,
                        case_id: location.state.case_id,
                      },
                    })
                  }
                  className="flex-1 py-2.5 text-white font-semibold rounded-lg transition text-center inline-flex items-center justify-center gap-2 hover:opacity-90"
                  style={{ backgroundColor: '#16A34A' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#15803D')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#16A34A')}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                  </svg>
                  View on Map
                </button>
                <button
                  onClick={() => navigate('/dispatch')}
                  className="flex-1 py-2.5 font-semibold rounded-lg transition text-center border-2 hover:bg-opacity-10"
                  style={{ borderColor: '#0A1628', color: '#0A1628' }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(10,22,40,0.05)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  New Dispatch
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  )
}
