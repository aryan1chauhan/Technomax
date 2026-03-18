import { useLocation, useNavigate, Navigate } from 'react-router-dom'

export default function Result() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state

  if (!data) {
    return <Navigate to="/dispatch" replace />
  }

  const handleLogout = () => {
    localStorage.removeItem('token')
    navigate('/login')
  }

  const scorePercent = Math.round(data.final_score * 100)

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
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

      {/* Main Content */}
      <main className="max-w-2xl mx-auto px-4 py-10">
        <div className="bg-white rounded-2xl shadow-lg p-8">

          {/* Success Badge */}
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center">
              <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <span className="text-sm font-semibold text-green-700">Best Hospital Found</span>
          </div>

          {/* Hospital Name & Address */}
          <h2 className="text-2xl font-bold text-gray-900">{data.hospital_name}</h2>
          <p className="text-sm text-gray-500 mt-1 mb-6">{data.address}</p>

          {/* Score Bar */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-medium text-gray-700">Match Score</span>
              <span className="text-sm font-bold text-blue-600">{scorePercent}%</span>
            </div>
            <div className="w-full h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 rounded-full transition-all duration-500"
                style={{ width: `${scorePercent}%` }}
              ></div>
            </div>
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-3 gap-3 mb-6">
            <div className="bg-gray-50 rounded-xl p-4 text-center border border-gray-100">
              <p className="text-xs text-gray-500 mb-1">Distance</p>
              <p className="text-lg font-bold text-gray-900">{data.distance_km} km</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4 text-center border border-gray-100">
              <p className="text-xs text-gray-500 mb-1">ETA</p>
              <p className="text-lg font-bold text-gray-900">{data.eta_minutes} min</p>
            </div>
            <div className="bg-gray-50 rounded-xl p-4 text-center border border-gray-100">
              <p className="text-xs text-gray-500 mb-1">Beds Available</p>
              <p className="text-lg font-bold text-gray-900">{data.beds_available}</p>
            </div>
          </div>

          {/* Equipment Matched */}
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-2">Equipment Matched</p>
            <div className="flex flex-wrap gap-2">
              {data.equipment_matched && data.equipment_matched.length > 0 ? (
                data.equipment_matched.map((item) => (
                  <span
                    key={item}
                    className="px-3 py-1 bg-green-100 text-green-700 text-xs font-semibold rounded-full uppercase"
                  >
                    {item.replace('_', ' ')}
                  </span>
                ))
              ) : (
                <span className="text-sm text-gray-400">None requested</span>
              )}
            </div>
          </div>

          {/* Equipment Missing */}
          <div className="mb-8">
            <p className="text-sm font-medium text-gray-700 mb-2">Equipment Missing</p>
            <div className="flex flex-wrap gap-2">
              {data.equipment_missing && data.equipment_missing.length > 0 ? (
                data.equipment_missing.map((item) => (
                  <span
                    key={item}
                    className="px-3 py-1 bg-red-100 text-red-700 text-xs font-semibold rounded-full uppercase"
                  >
                    {item.replace('_', ' ')}
                  </span>
                ))
              ) : (
                <span className="inline-flex items-center gap-1 text-sm text-green-600 font-medium">
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
                    hospital_name: data.hospital_name,
                    lat: data.lat,
                    lng: data.lng,
                    distance_km: data.distance_km,
                    eta_minutes: data.eta_minutes,
                  },
                })
              }
              className="flex-1 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition text-center"
            >
              View on Map
            </button>
            <button
              onClick={() => navigate('/dispatch')}
              className="flex-1 py-2.5 bg-gray-100 hover:bg-gray-200 text-gray-700 font-semibold rounded-lg transition text-center border border-gray-200"
            >
              New Dispatch
            </button>
          </div>
        </div>
      </main>
    </div>
  )
}
