import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { jwtDecode } from 'jwt-decode'
import api from '../../api/axios'

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
    localStorage.removeItem('token')
    navigate('/login')
  }

  const getTimeAgo = (dateString) => {
    const min = Math.round((new Date() - new Date(dateString)) / 60000)
    if (min === 0) return 'Just now'
    if (min < 60) return `${min} min${min !== 1 ? 's' : ''} ago`
    const hrs = Math.floor(min / 60)
    return `${hrs}h ${min % 60}m ago`
  }

  const getSeverityBadge = (condition) => {
    const high = ['cardiac arrest', 'stroke', 'trauma', 'severe trauma', 'respiratory failure', 'head injury', 'internal bleeding', 'spinal injury', 'chest injury', 'severe bleeding']
    const med = ['burns', 'anaphylaxis', 'kidney failure', 'pelvic injury', 'hypoglycemic crisis']
    const c = (condition || '').toLowerCase()
    if (high.includes(c)) return { bg: 'bg-red-100', text: 'text-red-700', border: 'border-red-200' }
    if (med.includes(c)) return { bg: 'bg-orange-100', text: 'text-orange-700', border: 'border-orange-200' }
    return { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-200' }
  }

  const todayCases = cases.filter(c => {
    const date = new Date(c.created_at)
    const today = new Date()
    return date.getDate() === today.getDate() && date.getMonth() === today.getMonth() && date.getFullYear() === today.getFullYear()
  })

  const activeCases = cases.filter(c => c.eta_minutes > 0)
  const completedCases = cases.filter(c => c.eta_minutes === 0)

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
        @keyframes live-dot {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.6); opacity: 0.4; }
        }
        .animate-live-dot { animation: live-dot 1.5s ease-in-out infinite; }
      `}</style>

      <div className="min-h-screen" style={{ backgroundColor: '#F8FAFC' }}>
        {/* HEADER */}
        <header className="px-6 py-4 flex items-center justify-between shadow-lg" style={{ backgroundColor: '#0A1628' }}>
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: '#16A34A' }}>
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 4v16m8-8H4" />
              </svg>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">MediRoute</h1>
              <p className="text-xs text-gray-400">Hospital Dashboard</p>
            </div>
            {activeCases.length > 0 && (
              <span className="ml-4 inline-flex items-center gap-1.5 px-3 py-1 bg-red-600 text-white text-xs font-bold rounded-full animate-pulse-incoming">
                <span className="w-1.5 h-1.5 bg-white rounded-full"></span>
                {activeCases.length} INCOMING
              </span>
            )}
          </div>
          <div className="flex items-center gap-4">
            {/* Live refresh indicator */}
            <div className="flex items-center gap-1.5">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full rounded-full animate-live-dot" style={{ backgroundColor: '#4ADE80' }}></span>
                <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: '#16A34A' }}></span>
              </span>
              <span className="text-xs text-gray-400 font-medium">Live — refreshing every 10s</span>
            </div>
            <button onClick={handleLogout} className="text-sm text-gray-400 hover:text-white font-medium transition px-3 py-1.5 rounded-lg hover:bg-white/10">
              Logout
            </button>
          </div>
        </header>

        {/* STATS BAR */}
        <div className="px-6 py-5 grid grid-cols-3 gap-4 max-w-5xl mx-auto">
          <div className="rounded-xl p-5 shadow-lg text-white" style={{ backgroundColor: '#0A1628' }}>
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-1">Cases Today</p>
            <p className="text-4xl font-extrabold">{todayCases.length}</p>
          </div>
          <div className="rounded-xl p-5 shadow-lg text-white" style={{ backgroundColor: '#0A1628' }}>
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-1">Active</p>
            <p className="text-4xl font-extrabold" style={{ color: '#4ADE80' }}>{activeCases.length}</p>
          </div>
          <div className="rounded-xl p-5 shadow-lg text-white" style={{ backgroundColor: '#0A1628' }}>
            <p className="text-gray-400 text-xs font-bold uppercase tracking-wider mb-1">Completed</p>
            <p className="text-4xl font-extrabold">{completedCases.length}</p>
          </div>
        </div>

        {/* CASES LIST */}
        <main className="px-6 pb-12 max-w-5xl mx-auto">
          <h2 className="text-2xl font-bold mb-6" style={{ color: '#0A1628' }}>Incoming Emergency Cases</h2>

          {loading ? (
            <div className="flex justify-center py-24">
              <div className="w-12 h-12 border-4 border-t-transparent rounded-full animate-spin" style={{ borderColor: '#16A34A', borderTopColor: 'transparent' }}></div>
            </div>
          ) : cases.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-gray-400">
              <svg className="w-16 h-16 mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-lg font-medium">No incoming cases</p>
              <p className="text-sm mt-1">Standing by for emergencies</p>
            </div>
          ) : (
            <div className="space-y-5">
              {cases.map(c => {
                const scorePercent = Math.round((c.final_score || 0) * 100)
                const scoreColor = scorePercent > 70 ? '#16A34A' : scorePercent >= 50 ? '#F59E0B' : '#EF4444'
                const severity = getSeverityBadge(c.condition)
                const isArrived = c.eta_minutes === 0

                return (
                  <div
                    key={c.id}
                    className="bg-white rounded-xl shadow-xl overflow-hidden border-l-4"
                    style={{ borderLeftColor: isArrived ? '#16A34A' : '#EF4444' }}
                  >
                    {/* Top bar */}
                    <div className="px-6 py-3 flex items-center justify-between bg-gray-50 border-b border-gray-100">
                      <div className="flex items-center gap-2">
                        {!isArrived && <span className="w-2.5 h-2.5 bg-red-500 rounded-full animate-pulse-incoming"></span>}
                        <span className={`px-2.5 py-0.5 rounded text-xs font-bold tracking-wide ${isArrived ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
                          {isArrived ? 'ARRIVED' : 'INCOMING'}
                        </span>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-gray-500 font-mono text-sm font-semibold">Case #{c.id}</span>
                        <span className="text-gray-400 text-xs">{getTimeAgo(c.created_at)}</span>
                      </div>
                    </div>

                    {/* Condition + Equipment */}
                    <div className="px-6 py-4 border-b border-gray-100">
                      <div className="flex items-center gap-3 mb-3">
                        <span className={`px-3 py-1 rounded-lg text-sm font-bold uppercase border ${severity.bg} ${severity.text} ${severity.border}`}>
                          {c.condition}
                        </span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {c.equipment_needed?.length > 0 ? (
                          c.equipment_needed.map(eq => (
                            <span key={eq} className="px-3 py-1 bg-gray-100 text-gray-600 text-xs font-semibold rounded-md uppercase">
                              {eq.replace('_', ' ')}
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
                          <p className="text-lg font-bold">{isArrived ? '✓' : `${c.eta_minutes} min`}</p>
                          <p className="text-xs text-gray-400 font-medium">{isArrived ? 'Arrived' : 'ETA'}</p>
                        </div>
                      </div>
                    </div>

                    {/* Action Button */}
                    <div className="px-6 py-4">
                      <button
                        onClick={() => navigate(`/hospital/track/${c.id}`, { state: c })}
                        className="w-full py-3.5 text-white font-bold rounded-lg transition flex items-center justify-center gap-2 text-base"
                        style={{ backgroundColor: '#16A34A' }}
                        onMouseEnter={e => e.target.style.backgroundColor = '#15803D'}
                        onMouseLeave={e => e.target.style.backgroundColor = '#16A34A'}
                      >
                        🚑 Track Ambulance
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
