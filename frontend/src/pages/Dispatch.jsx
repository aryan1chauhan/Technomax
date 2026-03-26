import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../api/axios'
import TerminalLayout from '../components/TerminalLayout'
import TerminalBox from '../components/TerminalBox'

const CONDITIONS = [
  'cardiac arrest', 'stroke', 'trauma', 'severe trauma',
  'respiratory failure', 'head injury', 'internal bleeding',
  'spinal injury', 'chest injury', 'severe bleeding', 'burns',
  'anaphylaxis', 'kidney failure', 'pelvic injury',
  'hypoglycemic crisis', 'fractures', 'soft tissue injury',
  'facial injury', 'psychological trauma', 'broken bone'
];

const EQUIPMENT_OPTIONS = [
  'ecg',
  'ventilator',
  'defibrillator',
  'xray',
  'icu',
  'blood_bank',
];

export default function Dispatch() {
  const [condition, setCondition] = useState('')
  const [equipment, setEquipment] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [ambulanceLat, setAmbulanceLat] = useState(null)
  const [ambulanceLng, setAmbulanceLng] = useState(null)
  const [locationError, setLocationError] = useState('')
  const [locationLoading, setLocationLoading] = useState(false)
  const [aiInput, setAiInput] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiReasoning, setAiReasoning] = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    setLocationLoading(true)
    if (!navigator.geolocation) {
      setLocationError('GPS not supported')
      setLocationLoading(false)
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setAmbulanceLat(position.coords.latitude)
        setAmbulanceLng(position.coords.longitude)
        setLocationLoading(false)
      },
      (error) => {
        setLocationError('Using default loc (Roorkee)')
        setAmbulanceLat(29.8543)
        setAmbulanceLng(77.8880)
        setLocationLoading(false)
      },
      { enableHighAccuracy: true, timeout: 10000 }
    )
  }, [])

  const toggleEquipment = (item) => {
    setEquipment((prev) =>
      prev.includes(item) ? prev.filter((e) => e !== item) : [...prev, item]
    )
  }

  const handleAiAnalyze = async () => {
    if (!aiInput) return;
    setAiLoading(true);
    setError('');
    try {
      const res = await api.post('/api/ai/analyze', { input: aiInput });
      if (res.data.error) {
        setError(res.data.error + " (Manual fallback active)");
      } else {
        const parsed = res.data.result;
        
        // Match condition
        const cond = (parsed.condition || '').toLowerCase();
        const match = CONDITIONS.find(c => c.includes(cond) || cond.includes(c));
        if (match) setCondition(match);
        else if (CONDITIONS.includes(parsed.condition)) setCondition(parsed.condition);
        
        // Match equipment
        if (Array.isArray(parsed.equipment)) {
          const validEq = parsed.equipment.filter(e => EQUIPMENT_OPTIONS.includes(e));
          setEquipment(validEq);
        }
        
        if (parsed.reasoning) setAiReasoning(parsed.reasoning);
      }
    } catch (err) {
      setError("⚠️ AI FAILED — MANUAL OVERRIDE ENGAGED");
      setAiReasoning('');
    } finally {
      setAiLoading(false);
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!condition) {
      setError('Select a condition')
      return
    }
    setError('')
    setLoading(true)

    try {
      const res = await api.post('/api/dispatch/', {
        condition,
        equipment_needed: equipment,
        ambulance_lat: ambulanceLat,
        ambulance_lng: ambulanceLng,
      })
      navigate('/result', { 
        state: { 
          ...res.data, 
          case_id: res.data.case_id,
          ambulance_lat: ambulanceLat,
          ambulance_lng: ambulanceLng
        } 
      })
    } catch (err) {
      setError(
        err.response?.data?.detail || 'Dispatch failed'
      )
    } finally {
      setLoading(false)
    }
  }

  const getPriority = (cond) => {
    if (!cond) return { level: 'WAITING', label: 'Awaiting Assessment', icon: '⏱️', class: 'status-disconnected' };
    const level3 = ['cardiac arrest', 'stroke', 'severe trauma', 'respiratory failure', 'head injury', 'internal bleeding', 'spinal injury', 'chest injury', 'severe bleeding', 'anaphylaxis'];
    const level2 = ['trauma', 'burns', 'kidney failure', 'pelvic injury', 'hypoglycemic crisis', 'fractures'];
    const level1 = ['soft tissue injury', 'facial injury', 'psychological trauma', 'broken bone'];
    
    if (level3.includes(cond)) return { level: 'CRITICAL', label: 'Critical Response', icon: '🚨', class: 'status-critical' };
    if (level2.includes(cond)) return { level: 'WARNING', label: 'Urgent Response', icon: '⚠️', class: 'status-warning' };
    if (level1.includes(cond)) return { level: 'STABLE', label: 'Standard Response', icon: '⚕️', class: 'status-stable' };
    
    return { level: 'UNKNOWN', label: 'Evaluating...', icon: '⏱️', class: 'status-disconnected' };
  }

  const priority = getPriority(condition);

  return (
    <TerminalLayout pageTitle="Ambulance Control Panel">
      <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem 1rem' }}>
        <TerminalBox title="🚑 Dispatch Command Center" width="600px">
          
          <div className="glass-section" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Location Status</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
                {locationLoading ? (
                  <><span className="status-badge status-warning">Wait</span> Acquiring Satellites...</>
                ) : ambulanceLat && !locationError ? (
                  <><span className="status-badge status-stable">Live</span> Active Tracking</>
                ) : (
                  <><span className="status-badge status-warning">Static</span> {locationError || 'Signal Lost'}</>
                )}
              </div>
            </div>
            {ambulanceLat && (
              <div style={{ textAlign: 'right' }}>
                <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Coordinates</div>
                <div style={{ fontFamily: 'monospace', color: 'var(--term-primary)' }}>
                  {ambulanceLat.toFixed(4)}° N, {ambulanceLng.toFixed(4)}° E
                </div>
              </div>
            )}
          </div>

          <div className="glass-section" style={{ border: '1px solid var(--term-primary)', background: 'rgba(59, 130, 246, 0.05)' }}>
            <div style={{ marginBottom: '0.75rem', fontWeight: 600, color: 'var(--term-primary)' }}>🤖 AI Triage Assistant</div>
            <textarea 
              value={aiInput}
              onChange={e => setAiInput(e.target.value)}
              className="premium-input"
              rows="2"
              style={{ width: '100%', padding: '0.75rem', marginBottom: '0.75rem', background: 'rgba(0,0,0,0.3)', color: 'white', resize: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '6px' }}
              placeholder="Describe emergency (e.g. 'Patient fell, unconscious, heavy head bleeding...')"
              disabled={aiLoading}
            />
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
               <button 
                 onClick={(e) => { e.preventDefault(); handleAiAnalyze(); }} 
                 disabled={aiLoading || !aiInput}
                 style={{ background: 'var(--term-primary)', color: 'black', padding: '0.5rem 1rem', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', transition: 'opacity 0.2s', opacity: (aiLoading || !aiInput) ? 0.5 : 1 }}
               >
                 {aiLoading ? 'ANALYZING...' : 'PARSE WITH CLAUDE'}
               </button>
               {aiReasoning && (
                 <div style={{ flex: 1, marginLeft: '1rem', fontSize: '0.8rem', color: 'var(--term-primary)', fontStyle: 'italic', lineHeight: '1.2' }}>
                   ↳ {aiReasoning}
                 </div>
               )}
            </div>
          </div>

          <div className="glass-section mt-4">
            <div style={{ marginBottom: '0.75rem', fontWeight: 600, color: 'var(--term-text)' }}>Patient Condition (Manual Override)</div>
            <select
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
              className="premium-input"
              style={{ padding: '1rem', appearance: 'menulist' }}
            >
              <option value="" disabled>Select primary patient condition...</option>
              {CONDITIONS.map((c) => (
                <option key={c} value={c}>
                  {c.split(' ').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                </option>
              ))}
            </select>
          </div>

          <div className="glass-section">
            <div style={{ marginBottom: '0.75rem', fontWeight: 600, color: 'var(--term-text)' }}>Required Equipment</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.75rem' }}>
              {EQUIPMENT_OPTIONS.map((item) => {
                const isChecked = equipment.includes(item);
                return (
                  <label key={item} className={`custom-checkbox ${isChecked ? 'checked' : ''}`}>
                    <div style={{ 
                      width: '18px', height: '18px', borderRadius: '4px', 
                      border: `1px solid ${isChecked ? 'var(--term-primary)' : 'rgba(255,255,255,0.2)'}`,
                      background: isChecked ? 'var(--term-primary)' : 'transparent',
                      display: 'flex', alignItems: 'center', justifyContent: 'center'
                    }}>
                      {isChecked && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>}
                    </div>
                    <input
                      type="checkbox"
                      checked={isChecked}
                      onChange={() => toggleEquipment(item)}
                      style={{ display: 'none' }}
                    />
                    <span style={{ fontSize: '0.875rem', fontWeight: isChecked ? 600 : 400, color: isChecked ? '#fff' : 'var(--term-text-muted)', textTransform: 'capitalize' }}>
                      {item.replace('_', ' ')}
                    </span>
                  </label>
                )
              })}
            </div>
          </div>

          <div className="glass-section" style={{ background: 'rgba(0,0,0,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div style={{ color: 'var(--term-text-muted)', fontSize: '0.875rem', marginBottom: '0.25rem' }}>Assessed Priority</div>
              <span className={`status-badge ${priority.class}`} style={{ fontSize: '1rem', padding: '0.4rem 1rem' }}>
                {priority.icon} {priority.label}
              </span>
            </div>
            
            <button
              onClick={handleSubmit}
              disabled={loading || locationLoading || !ambulanceLat || !condition}
              className="term-btn"
              style={{ padding: '0.875rem 2rem' }}
            >
              {loading ? 'Dispatching...' : 'Dispatch Ambulance'}
            </button>
          </div>
          
          {error && (
            <div style={{
              padding: '1rem',
              color: 'var(--term-red)',
              fontSize: '0.875rem',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239,68,68,0.4)',
              borderRadius: '6px',
              fontWeight: error.includes('AI FAILED') ? 700 : 400,
              letterSpacing: error.includes('AI FAILED') ? '0.05em' : 'normal',
              textAlign: 'center'
            }}>
              {error}
            </div>
          )}

        </TerminalBox>
      </div>
    </TerminalLayout>
  )
}
