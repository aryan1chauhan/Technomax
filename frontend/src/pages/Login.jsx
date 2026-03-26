import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { jwtDecode } from 'jwt-decode'
import api from '../api/axios'
import TerminalLayout from '../components/TerminalLayout'
import TerminalBox from '../components/TerminalBox'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await api.post('/api/auth/login', { email, password })
      localStorage.setItem('token', res.data.access_token)
      
      const decoded = jwtDecode(res.data.access_token)
      const role = decoded.role || decoded.sub
      
      if (role === 'admin') navigate('/admin/dashboard')
      else if (role === 'hospital') navigate('/hospital/dashboard')
      else navigate('/dispatch')
    } catch (err) {
      setError('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  let statusIcon = '🔴';
  let statusText = 'Not Authenticated';
  let statusClass = 'status-critical';

  if (loading) {
    statusIcon = '🟡';
    statusText = 'Authenticating...';
    statusClass = 'status-warning';
  } else if (error) {
    statusIcon = '🔴';
    statusText = 'Invalid credentials';
    statusClass = 'status-critical';
  }

  return (
    <TerminalLayout pageTitle="ACCESS NODE">
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '80vh', position: 'relative' }}>
        
        {/* Decorative glow behind the box */}
        <div style={{
          position: 'absolute',
          width: '300px',
          height: '300px',
          background: 'var(--term-primary)',
          filter: 'blur(100px)',
          opacity: 0.15,
          borderRadius: '50%',
          zIndex: 0
        }}></div>

        <div style={{ zIndex: 1, width: '100%', display: 'flex', justifyContent: 'center' }}>
          <TerminalBox title="🔐 System Login Required" width="400px">
            <div className="glass-section">
              <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  <label style={{ color: 'var(--term-text-muted)', fontSize: '0.9rem', fontWeight: 500 }}>Email Address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    className="premium-input"
                    placeholder="you@example.com"
                    disabled={loading}
                    required
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                  <label style={{ color: 'var(--term-text-muted)', fontSize: '0.9rem', fontWeight: 500 }}>Password</label>
                  <input
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    className="premium-input"
                    placeholder="••••••••"
                    disabled={loading}
                    required
                  />
                </div>

                <div style={{ marginTop: '0.5rem' }}>
                  <button 
                    type="submit" 
                    className="term-btn"
                    disabled={loading}
                    style={{ width: '100%' }}
                  >
                    Authenticate
                  </button>
                </div>
              </form>
            </div>

            <div className="glass-section" style={{ background: 'rgba(0,0,0,0.1)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--term-text-muted)', fontSize: '0.9rem' }}>Status</span>
                <span className={`status-badge ${statusClass}`}>{statusIcon} {statusText}</span>
              </div>
            </div>
            
          </TerminalBox>
        </div>
      </div>
    </TerminalLayout>
  )
}
