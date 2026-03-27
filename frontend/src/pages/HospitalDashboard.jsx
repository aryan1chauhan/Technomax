import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/axios'

export default function HospitalDashboard() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  const fetchCases = async () => {
    try {
      const token = localStorage.getItem('token')
      if (!token) {
        navigate('/login')
        return
      }

      // FIX #4: Use /api/cases/hospital (not /api/cases/) so hospital users
      // see cases assigned to their hospital, not cases they dispatched
      const res = await api.get('/api/cases/hospital')
      let data = res.data
      if (!Array.isArray(data)) {
        data = data.items || []
      }

      data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      setCases(data)
    } catch (err) {
      console.error('Failed to fetch cases', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCases()
    const interval = setInterval(fetchCases, 10000)
    return () => clearInterval(interval)
  }, [])

  const handleLogout = () => {
    // FIX (bonus): Use removeItem instead of clear() to avoid wiping unrelated storage
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    navigate('/login')
  }

  const getTimeAgo = (dateString) => {
    const min = Math.round((new Date() - new Date(dateString)) / 60000)
    if (min === 0) return 'Just now'
    return `${min} min${min !== 1 ? 's' : ''} ago`
  }

  const todayCases = cases.filter(c => {
    const date = new Date(c.created_at)
    const today = new Date()
    return date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear()
  })

  const activeCases = cases

  const avgScore = cases.length > 0
    ? Math.round((cases.reduce((acc, c) => acc + (c.final_score || 0), 0) / cases.length) * 100)
    : 0

  return (
    <>
      <style>{`
        @keyframes pulse-incoming {
          0%, 100% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.15); }
        }
        .animate-pulse-incoming { animation: pulse-incoming 1.5s ease-in-out infinite; }
        @keyframes bar-fill { from { width: 0%; } }
        .animate-bar-fill { animation: bar-fill 1.2s ease-out forwards; }
      `}</style>

      <div className="min-h-screen bg-[#0F1B2D] text-white">
        {/* HEADER */}
        <header className="px-6 py-4 flex items-center justify-between shadow-lg" style={{ backgroundColor: '#0A1628' }}>
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
            {cases.length > 0 && (
              <span className="ml-4 inline-flex items-center gap-1.5 px-3 py-1 bg-red-600 text-white text-xs font-bold rounded-full animate-pulse-incoming">
                <span className="w-1.5 h-1.5 bg-white rounded-full"></span>
                INCOMING
              </span>
            )}
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-white font-medium transition px-3 py-1.5 rounded-lg hover:bg-white/10"
          >
            Logout
          </button>
        </header>

        {/* STATS ROW */}
        <div className="px-6 py-5 grid grid-cols-3 gap-4 max-w-5xl mx-auto">
          <div className="rounded-xl p-5 shadow-lg" style={{ backgroundColor: '#0A1628' }}>
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-1">Cases Today</p>
            <p className="text-4xl font-extrabold">{todayCases.length}</p>
          </div>
          <div className="rounded-xl p-5 shadow-lg" style={{ backgroundColor: '#0A1628' }}>
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-1">Active Cases</p>
            <p className="text-4xl font-extrabold text-[#4ADE80]">{activeCases.length}</p>
          </div>
          <div className="rounded-xl p-5 shadow-lg" style={{ backgroundColor: '#0A1628' }}>
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-1">Average Score</p>
            <p className="text-4xl font-extrabold">{avgScore}%</p>
          </div>
        </div>

        {/* CASES LIST */}
        <main className="px-6 pb-12 max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold mb-6">Incoming Emergency Cases</h2>

          {loading ? (
            <div className="flex justify-center py-24">
              <div className="w-12 h-12 border-4 border-[#16A34A] border-t-transparent rounded-full animate-spin"></div>
            </div>
          ) : cases.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-gray-400">
              <span className="w-4 h-4 bg-[#16A34A] rounded-full animate-pulse-incoming mb-4"></span>
              <p className="text-lg">No cases assigned yet — standing by</p>
            </div>
          ) : (
            <div className="space-y-5">
              {cases.map(c => {
                const scorePercent = Math.round((c.final_score || 0) * 100)
                const scoreColor = scorePercent > 70 ? '#16A34A' : scorePercent >= 50 ? '#F59E0B' : '#EF4444'

                return (
                  <div key={c.id} className="bg-white rounded-xl shadow-xl overflow-hidden border-l-4" style={{ borderLeftColor: '#EF4444' }}>
                    {/* Top bar */}
                    <div className="px-6 py-3 flex items-center justify-between bg-gray-50 border-b border-gray-100">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse-incoming"></span>
                        <span className="bg-red-600 text-white px-2.5 py-0.5 rounded text-xs font-bold tracking-wide">INCOMING</span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-gray-500 font-mono text-sm font-semibold">Case #{c.id}</span>
                        <span className="text-gray-400 text-xs">{getTimeAgo(c.created_at)}</span>
                      </div>
                    </div>

                    {/* Condition + Equipment */}
                    <div className="px-6 py-4 border-b border-gray-100">
                      <p className="text-2xl font-extrabold uppercase text-red-600 mb-3">{c.condition}</p>
                      <div className="flex flex-wrap gap-2">
                        {c.equipment_needed?.length > 0 ? (
                          c.equipment_needed.map(eq => (
                            <span key={eq} className="px-3 py-1 bg-[#DCFCE7] text-[#15803D] text-xs font-bold rounded-md uppercase">
                              {eq.replace(/_/g, ' ')}
                            </span>
                          ))
                        ) : (
                          <span className="text-sm text-gray-400">No equipment specified</span>
                        )}
                      </div>
                    </div>

                    {/* Score / Distance / ETA */}
                    <div className="px-6 py-4 flex items-center gap-8 border-b border-gray-100">
                      <div className="flex items-center gap-3 flex-1">
                        <span className="text-sm font-bold text-gray-500">Score</span>
                        <span className="text-lg font-extrabold" style={{ color: scoreColor }}>{scorePercent}%</span>
                        <div className="h-2.5 flex-1 bg-gray-200 rounded-full overflow-hidden">
                          <div className="h-full rounded-full animate-bar-fill" style={{ width: `${scorePercent}%`, backgroundColor: scoreColor }}></div>
                        </div>
                      </div>
                      <div className="flex items-center gap-6 text-gray-700">
                        <div className="text-center">
                          <p className="text-lg font-bold">{c.distance_km} km</p>
                          <p className="text-xs text-gray-400 font-medium">Distance</p>
                        </div>
                        <div className="text-center">
                          <p className="text-lg font-bold">{c.eta_minutes} min</p>
                          <p className="text-xs text-gray-400 font-medium">ETA</p>
                        </div>
                      </div>
                    </div>

                    {/* Action */}
                    <div className="px-6 py-4">
                      <button
                        onClick={() => navigate(`/hospital/track/${c.id}`)}
                        className="w-full py-3.5 bg-[#16A34A] hover:bg-[#15803D] text-white font-bold rounded-lg transition flex items-center justify-center gap-2 text-base"
                      >
                        🚑 View Emergency &amp; Track Ambulance
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </main>
      </div>
    </>
  )
}
