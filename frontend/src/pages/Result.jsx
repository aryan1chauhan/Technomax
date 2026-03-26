import { useLocation, useNavigate, Navigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import TerminalLayout from '../components/TerminalLayout'
import TerminalBox from '../components/TerminalBox'

export default function Result() {
  const location = useLocation()
  const navigate = useNavigate()
  const data = location.state
  const [animatedScore, setAnimatedScore] = useState(0)

  if (!data) {
    return <Navigate to="/dispatch" replace />
  }

  const scorePercent = Math.round(data.final_score * 100)
  
  useEffect(() => {
    const timer = setTimeout(() => setAnimatedScore(scorePercent), 100)
    return () => clearTimeout(timer)
  }, [scorePercent])

  const numFilled = Math.round(animatedScore / 10)
  const numEmpty = 10 - numFilled
  const asciiBar = '█'.repeat(Math.max(0, numFilled)) + '░'.repeat(Math.max(0, numEmpty))
  
  const scoreColor = animatedScore > 70 ? 'var(--term-green)' : animatedScore >= 50 ? 'var(--term-yellow)' : 'var(--term-red)'

  // Use case ID if available, otherwise mock one
  const caseId = data.case_id ? String(data.case_id).padStart(3, '0') : '001'

  // Combine matched and missing for display
  const allEquipment = []
  if (data.equipment_matched) {
    data.equipment_matched.forEach(item => {
      allEquipment.push({ name: item, status: 'matched' })
    })
  }
  if (data.equipment_missing) {
    data.equipment_missing.forEach(item => {
      allEquipment.push({ name: item, status: 'missing' })
    })
  }

  return (
    <TerminalLayout pageTitle="Ambulance Dispatch Result">
      <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem 1rem' }}>
        <TerminalBox title={`📋 DISPATCH RESULT - CASE #${caseId}`} width="600px">
          
          <div className="glass-section" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(16, 185, 129, 0.05)' }}>
            <div style={{ fontWeight: 600, color: 'var(--term-text-muted)' }}>STATUS</div>
            <div className="status-badge status-stable" style={{ fontSize: '1rem', padding: '0.5rem 1rem' }}>
              🟢 HOSPITAL ASSIGNED
            </div>
          </div>

          <div className="glass-section">
            <div style={{ marginBottom: '1rem', fontWeight: 600, letterSpacing: '0.05em', color: 'var(--term-primary)' }}>ASSIGNED HOSPITAL</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              <div style={{ display: 'flex' }}>
                <span style={{ width: '100px', color: 'var(--term-text-muted)' }}>Name:</span> 
                <span style={{ fontWeight: 600, fontSize: '1.1rem', color: 'var(--term-text)' }}>{data.hospital_name || data.name}</span>
              </div>
              <div style={{ display: 'flex' }}>
                <span style={{ width: '100px', color: 'var(--term-text-muted)' }}>Address:</span> 
                <span style={{ color: 'var(--term-text)' }}>{data.address || 'Location Unavailable'}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', marginTop: '0.75rem' }}>
                <span style={{ width: '100px', color: 'var(--term-text-muted)' }}>Match Score:</span> 
                <span style={{ color: scoreColor, fontFamily: 'monospace', letterSpacing: '1px', fontSize: '1.25rem', textShadow: `0 0 10px ${scoreColor}` }}>
                  {asciiBar}
                </span>
                <span style={{ marginLeft: '1rem', fontWeight: 700, color: scoreColor }}>{animatedScore}%</span>
              </div>
            </div>
          </div>

          <div className="glass-section">
            <div style={{ marginBottom: '1rem', fontWeight: 600, letterSpacing: '0.05em', color: 'var(--term-primary)' }}>VITALS</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
                <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>Distance</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--term-text)' }}>{data.distance_km} <span style={{ fontSize: '0.9rem', color: 'var(--term-text-muted)', fontWeight: 400 }}>km</span></div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
                <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>ETA</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--term-text)' }}>{data.eta_minutes} <span style={{ fontSize: '0.9rem', color: 'var(--term-text-muted)', fontWeight: 400 }}>min</span></div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.05)', textAlign: 'center' }}>
                <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>Beds</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--term-text)' }}>{data.beds_available ?? data.beds ?? 0} <span style={{ fontSize: '0.9rem', color: 'var(--term-text-muted)', fontWeight: 400 }}>avail</span></div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.15)', textAlign: 'center' }}>
                <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.5rem' }}>Confidence</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--term-green)' }}>
                  {data.confidence ? `${Math.round(data.confidence * 100)}%` : 'N/A'}
                </div>
              </div>
            </div>
          </div>

          <div className="glass-section">
            <div style={{ marginBottom: '1rem', fontWeight: 600, letterSpacing: '0.05em', color: 'var(--term-primary)' }}>EQUIPMENT STATUS</div>
            {allEquipment.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                {allEquipment.map((eq, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    {eq.status === 'matched' ? (
                      <><span style={{ color: 'var(--term-green)', fontWeight: 'bold' }}>✓</span> <span style={{ textTransform: 'capitalize', color: 'var(--term-text)' }}>{eq.name.replace('_', ' ')}</span></>
                    ) : (
                      <><span style={{ color: 'var(--term-red)', fontWeight: 'bold' }}>✗</span> <span style={{ textTransform: 'capitalize', color: 'var(--term-red)', opacity: 0.9 }}>{eq.name.replace('_', ' ')} (missing)</span></>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: 'var(--term-text-muted)', fontStyle: 'italic' }}>No specific equipment requested.</div>
            )}
          </div>

          {data.ml_reasoning && data.ml_reasoning.length > 0 && (
            <div className="glass-section mt-4" style={{ border: '1px solid var(--term-green)', background: 'rgba(16, 185, 129, 0.05)' }}>
              <h3 style={{ marginBottom: '0.75rem', fontWeight: 700, letterSpacing: '0.05em', color: 'var(--term-green)', margin: '0 0 10px 0', fontSize: '1rem' }}>🤖 AI INSIGHT</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {data.ml_reasoning.map((r, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--term-text)', fontSize: '0.9rem' }}>
                    <span style={{ color: 'var(--term-green)' }}>→</span> 
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="glass-section" style={{ display: 'flex', gap: '1rem' }}>
            <button
              onClick={() =>
                navigate('/map', {
                  state: {
                    ...location.state,
                    case_id: location.state.case_id,
                    ambulance_lat: location.state.ambulance_lat,
                    ambulance_lng: location.state.ambulance_lng,
                    lat: location.state.lat,
                    lng: location.state.lng
                  },
                })
              }
              className="term-btn"
              style={{ flex: 1, padding: '1rem' }}
            >
              [ VIEW LIVE MAP ]
            </button>
            <button
              onClick={() => navigate('/dispatch')}
              className="term-btn"
              style={{ flex: 1, padding: '1rem', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', boxShadow: 'none' }}
            >
              [ NEW DISPATCH ]
            </button>
          </div>
          
        </TerminalBox>
      </div>
    </TerminalLayout>
  )
}
