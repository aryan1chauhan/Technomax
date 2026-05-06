import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/Toast";
import { jwtDecode } from "jwt-decode";
import api from "../api/axios";

export default function Login() {
  const navigate = useNavigate();
  const { toast } = useToast();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [loading, setLoading] = useState(false);
  const [view, setView] = useState("login"); // "login" | "forgot"
  const [resetEmail, setResetEmail] = useState("");
  const [resetDone, setResetDone] = useState(false);

  // Live clock state
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const timeStr = now.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  const dateStr = now.toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email || !password) {
      toast("Enter email and password.", "error");
      return;
    }
    setLoading(true);
    try {
      const res = await api.post("/api/auth/login", { email, password }, { timeout: 60_000 });
      const { access_token } = res.data;
      
      localStorage.setItem("token", access_token);
      
      const decoded = jwtDecode(access_token);
      const role = decoded.role || "ambulance";
      
      localStorage.setItem("role", role);
      localStorage.setItem("email", decoded.sub);
      
      toast(`Welcome, ${role}.`, "success");
      
      if (role === "admin") navigate("/admin/dashboard");
      else if (role === "hospital") navigate("/hospital/dashboard");
      else if (role === "ambulance") navigate("/dispatch");
      else navigate("/dashboard");
    } catch (err) {
      if (err.response?.status === 401) {
        toast("Invalid credentials.", "error");
      } else if (err.code === "ERR_NETWORK" || err.code === "ECONNABORTED") {
        toast("Backend is cold-starting. Wait 30s and retry.", "warning", 8000);
      } else {
        toast(err.response?.data?.message || err.response?.data?.detail || "Login failed.", "error");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setLoading(true);
    await new Promise((r) => setTimeout(r, 1200));
    setLoading(false);
    setResetDone(true);
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400;500&display=swap');

        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

        .login-root {
          min-height: 100vh;
          display: flex;
          background: #0a0c10;
          font-family: 'DM Sans', sans-serif;
        }

        /* ── LEFT PANEL ── */
        .left-panel {
          flex: 1;
          position: relative;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 2.5rem;
          overflow: hidden;
          background: #080b12;
        }

        /* Mountain scene */
        .scene {
          position: absolute;
          inset: 0;
          overflow: hidden;
        }
        .scene svg { width: 100%; height: 100%; }

        /* Animated ambulance */
        .ambulance-wrap {
          position: absolute;
          bottom: 22%;
          animation: drive 18s linear infinite;
        }
        @keyframes drive {
          from { left: -80px; }
          to   { left: 110%; }
        }
        .siren-ring {
          position: absolute;
          top: 4px; left: 28px;
          width: 12px; height: 12px;
          border-radius: 50%;
          background: transparent;
          border: 2px solid rgba(255, 60, 60, 0.7);
          animation: ping 1s ease-out infinite;
        }
        .siren-ring:nth-child(2) { animation-delay: 0.3s; }
        @keyframes ping {
          0%   { transform: scale(1); opacity: 1; }
          100% { transform: scale(3); opacity: 0; }
        }

        /* ECG line */
        .ecg-wrap {
          position: absolute;
          bottom: 18%;
          left: 0; right: 0;
          height: 40px;
          overflow: hidden;
          opacity: 0.35;
        }
        .ecg-line {
          stroke: #3ecf8e;
          stroke-width: 1.5;
          fill: none;
          stroke-dasharray: 600;
          stroke-dashoffset: 600;
          animation: ecg 3s linear infinite;
        }
        @keyframes ecg {
          to { stroke-dashoffset: -600; }
        }

        /* Top badge */
        .dispatch-badge {
          position: relative;
          z-index: 10;
          display: inline-flex;
          align-items: center;
          gap: 0.5rem;
          background: rgba(255,255,255,0.06);
          border: 1px solid rgba(255,255,255,0.1);
          border-radius: 999px;
          padding: 0.4rem 1rem;
          font-family: 'DM Mono', monospace;
          font-size: 0.7rem;
          color: rgba(255,255,255,0.6);
          letter-spacing: 0.08em;
          width: fit-content;
        }
        .dispatch-badge .dot {
          width: 6px; height: 6px;
          border-radius: 50%;
          background: #3ecf8e;
          box-shadow: 0 0 6px #3ecf8e;
          animation: blink 2s ease-in-out infinite;
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.3; }
        }

        /* Bottom: clock block */
        .clock-block {
          position: relative;
          z-index: 10;
        }
        .clock-time {
          font-family: 'DM Mono', monospace;
          font-size: 3rem;
          font-weight: 500;
          color: #fff;
          letter-spacing: -0.02em;
          line-height: 1;
          margin-bottom: 0.4rem;
        }
        .clock-date {
          font-family: 'DM Sans', sans-serif;
          font-size: 0.8rem;
          font-weight: 300;
          color: rgba(255,255,255,0.45);
          letter-spacing: 0.04em;
          margin-bottom: 1.2rem;
        }
        .dispatch-status {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-family: 'DM Mono', monospace;
          font-size: 0.7rem;
          color: #3ecf8e;
          letter-spacing: 0.06em;
        }
        .dispatch-status::before {
          content: '';
          display: inline-block;
          width: 8px; height: 8px;
          border-radius: 50%;
          background: #3ecf8e;
          box-shadow: 0 0 8px #3ecf8e;
          animation: blink 2s ease-in-out infinite;
        }

        /* ── RIGHT PANEL ── */
        .right-panel {
          width: 420px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: 3rem 3rem 2.5rem;
          background: #f7f5f0;
          position: relative;
        }

        .brand-mark {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          margin-bottom: 3rem;
        }
        .brand-cross {
          width: 28px; height: 28px;
          background: #e63946;
          border-radius: 6px;
          display: flex; align-items: center; justify-content: center;
          flex-shrink: 0;
        }
        .brand-cross svg { color: #fff; }
        .brand-name {
          font-family: 'DM Mono', monospace;
          font-size: 0.75rem;
          font-weight: 500;
          color: #1a1a2e;
          letter-spacing: 0.12em;
          text-transform: uppercase;
        }

        .greeting {
          font-family: 'Syne', sans-serif;
          font-size: 2.4rem;
          font-weight: 800;
          color: #0f0f1a;
          line-height: 1.1;
          margin-bottom: 0.5rem;
        }
        .subtext {
          font-size: 0.85rem;
          color: #888;
          margin-bottom: 2.5rem;
          font-weight: 300;
        }

        .field-group {
          display: flex;
          flex-direction: column;
          gap: 1rem;
          margin-bottom: 1.5rem;
        }
        .field-label {
          display: block;
          font-size: 0.7rem;
          font-weight: 500;
          color: #999;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          margin-bottom: 0.35rem;
        }
        .field-input {
          width: 100%;
          padding: 0.75rem 1rem;
          border: 1.5px solid #e0ddd7;
          border-radius: 8px;
          background: #fff;
          font-family: 'DM Sans', sans-serif;
          font-size: 0.9rem;
          color: #0f0f1a;
          outline: none;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .field-input:focus {
          border-color: #0f0f1a;
          box-shadow: 0 0 0 3px rgba(15,15,26,0.06);
        }
        .pass-wrap {
          position: relative;
        }
        .pass-wrap .field-input {
          padding-right: 2.8rem;
        }
        .pass-toggle {
          position: absolute;
          right: 0.85rem;
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          cursor: pointer;
          color: #aaa;
          padding: 0;
          display: flex;
          align-items: center;
        }
        .pass-toggle:hover { color: #555; }

        .forgot-link {
          display: block;
          text-align: right;
          font-size: 0.78rem;
          color: #aaa;
          text-decoration: none;
          margin-top: -0.5rem;
          margin-bottom: 1.5rem;
          cursor: pointer;
          transition: color 0.2s;
        }
        .forgot-link:hover { color: #e63946; }

        .btn-login {
          width: 100%;
          padding: 0.85rem;
          background: #0f0f1a;
          color: #fff;
          border: none;
          border-radius: 8px;
          font-family: 'Syne', sans-serif;
          font-size: 0.95rem;
          font-weight: 700;
          letter-spacing: 0.04em;
          cursor: pointer;
          transition: background 0.2s, transform 0.1s;
          position: relative;
          overflow: hidden;
        }
        .btn-login:hover:not(:disabled) { background: #1e1e32; }
        .btn-login:active:not(:disabled) { transform: scale(0.99); }
        .btn-login:disabled { opacity: 0.6; cursor: not-allowed; }

        /* Forgot password view */
        .back-btn {
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          background: none;
          border: none;
          cursor: pointer;
          font-size: 0.8rem;
          color: #aaa;
          padding: 0;
          margin-bottom: 2rem;
          font-family: 'DM Sans', sans-serif;
          transition: color 0.2s;
        }
        .back-btn:hover { color: #0f0f1a; }

        .reset-success {
          background: #f0faf5;
          border: 1.5px solid #3ecf8e;
          border-radius: 10px;
          padding: 1.2rem 1.4rem;
          font-size: 0.85rem;
          color: #1a6644;
          line-height: 1.6;
        }

        .footer-note {
          position: absolute;
          bottom: 1.5rem;
          left: 3rem;
          right: 3rem;
          display: flex;
          justify-content: space-between;
          font-size: 0.68rem;
          color: #ccc;
          font-family: 'DM Mono', monospace;
        }

        /* Responsive */
        @media (max-width: 768px) {
          .left-panel { display: none; }
          .right-panel { width: 100%; padding: 2.5rem 1.75rem; }
        }
      `}</style>

      <div className="login-root">

        {/* ── LEFT PANEL ── */}
        <div className="left-panel">

          {/* Mountain scene */}
          <div className="scene">
            <svg viewBox="0 0 800 600" preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#060810"/>
                  <stop offset="60%" stopColor="#0d1224"/>
                  <stop offset="100%" stopColor="#111827"/>
                </linearGradient>
                <radialGradient id="glow" cx="50%" cy="70%" r="50%">
                  <stop offset="0%" stopColor="#e63946" stopOpacity="0.12"/>
                  <stop offset="100%" stopColor="transparent"/>
                </radialGradient>
              </defs>

              {/* Sky */}
              <rect width="800" height="600" fill="url(#sky)"/>
              <rect width="800" height="600" fill="url(#glow)"/>

              {/* Stars */}
              {[
                [80,40],[200,70],[350,30],[500,55],[660,35],[720,80],[150,110],
                [420,90],[570,50],[100,160],[300,140],[650,120],[750,45],[240,50],
              ].map(([x,y],i) => (
                <circle key={i} cx={x} cy={y} r="1" fill="white" opacity={0.4 + (i%3)*0.2}/>
              ))}

              {/* Far mountain range */}
              <polygon points="0,400 120,220 240,300 360,180 500,260 620,200 800,320 800,600 0,600"
                fill="#0c1120" opacity="0.9"/>
              {/* Mid mountains */}
              <polygon points="0,480 100,340 200,400 320,310 440,380 560,320 700,390 800,350 800,600 0,600"
                fill="#0e1428"/>
              {/* Foreground hills */}
              <polygon points="0,560 200,480 400,520 600,470 800,510 800,600 0,600"
                fill="#111827"/>

              {/* City buildings silhouette */}
              {[
                [20,530,18,30],[50,540,14,25],[80,525,20,35],[110,535,15,28],
                [600,528,18,32],[625,538,14,22],[650,520,22,40],[680,530,16,30],
                [710,535,12,25],[740,525,20,35],
              ].map(([x,y,w,h],i) => (
                <g key={i}>
                  <rect x={x} y={y-h} width={w} height={h} fill="#0a0e1a"/>
                  {/* lit windows */}
                  {Array.from({length: Math.floor(h/8)}).map((_,j) => (
                    Math.random() > 0.4 ?
                    <rect key={j} x={x+3} y={y-h+4+j*8} width={4} height={3}
                      fill="#f0c060" opacity="0.6"/> : null
                  ))}
                </g>
              ))}

              {/* Road */}
              <path d="M0,575 Q400,560 800,570" stroke="#1a2030" strokeWidth="8" fill="none"/>
              <path d="M0,575 Q400,560 800,570" stroke="#2a3245" strokeWidth="2" fill="none" strokeDasharray="30,20"/>
            </svg>

            {/* Ambulance */}
            <div className="ambulance-wrap">
              <div className="siren-ring"/>
              <div className="siren-ring"/>
              <svg width="64" height="32" viewBox="0 0 64 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="10" width="44" height="18" rx="3" fill="#e8edf5"/>
                <rect x="46" y="14" width="14" height="12" rx="2" fill="#d0d8e8"/>
                <rect x="4" y="12" width="20" height="10" rx="1" fill="#7ab8e8" opacity="0.8"/>
                <rect x="26" y="14" width="6" height="4" fill="#e63946" opacity="0.9"/>
                <text x="29" y="17.5" fontSize="3.5" fill="white" fontWeight="bold" textAnchor="middle">+</text>
                <circle cx="14" cy="28" r="4" fill="#333"/>
                <circle cx="14" cy="28" r="2" fill="#888"/>
                <circle cx="50" cy="28" r="4" fill="#333"/>
                <circle cx="50" cy="28" r="2" fill="#888"/>
                {/* Headlights */}
                <rect x="0" y="16" width="3" height="4" rx="1" fill="#fffbe0" opacity="0.9"/>
              </svg>
            </div>

            {/* ECG */}
            <div className="ecg-wrap">
              <svg width="100%" height="40" viewBox="0 0 800 40" preserveAspectRatio="none">
                <polyline className="ecg-line"
                  points="0,20 80,20 100,20 110,4 120,36 130,20 150,20 230,20 250,20 260,4 270,36 280,20 300,20 380,20 400,20 410,4 420,36 430,20 450,20 530,20 550,20 560,4 570,36 580,20 600,20 680,20 700,20 710,4 720,36 730,20 750,20 800,20"
                />
              </svg>
            </div>
          </div>

          {/* Top badge */}
          <div className="dispatch-badge">
            <span className="dot"/>
            DISPATCH NETWORK · UTTARAKHAND
          </div>

          {/* Bottom clock */}
          <div className="clock-block">
            <div className="clock-time">{timeStr}</div>
            <div className="clock-date">{dateStr}</div>
            <div className="dispatch-status">DISPATCH ACTIVE</div>
          </div>
        </div>

        {/* ── RIGHT PANEL ── */}
        <div className="right-panel">

          {view === "login" ? (
            <>
              <div className="brand-mark">
                <div className="brand-cross">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="5.5" y="0" width="3" height="14" fill="white"/>
                    <rect x="0" y="5.5" width="14" height="3" fill="white"/>
                  </svg>
                </div>
                <span className="brand-name">EMS · Uttarakhand</span>
              </div>

              <h1 className="greeting">Hi,<br/>Dispatcher.</h1>
              <p className="subtext">Sign in to access the response network.</p>

              <form onSubmit={handleSubmit}>
                <div className="field-group">
                  <div>
                    <label className="field-label">Email</label>
                    <input
                      className="field-input"
                      type="email"
                      placeholder="you@ems.gov.in"
                      value={email}
                      onChange={e => setEmail(e.target.value)}
                      autoComplete="email"
                    />
                  </div>
                  <div>
                    <label className="field-label">Password</label>
                    <div className="pass-wrap">
                      <input
                        className="field-input"
                        type={showPass ? "text" : "password"}
                        placeholder="••••••••"
                        value={password}
                        onChange={e => setPassword(e.target.value)}
                        autoComplete="current-password"
                      />
                      <button type="button" className="pass-toggle" onClick={() => setShowPass(p => !p)}>
                        {showPass ? (
                          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/>
                            <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/>
                            <line x1="1" y1="1" x2="23" y2="23"/>
                          </svg>
                        ) : (
                          <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                            <circle cx="12" cy="12" r="3"/>
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <span className="forgot-link" onClick={() => setView("forgot")}>
                  Forgot password?
                </span>

                <button className="btn-login" type="submit" disabled={loading}>
                  {loading ? "Authenticating…" : "Login →"}
                </button>
              </form>
            </>
          ) : (
            <>
              <button className="back-btn" onClick={() => { setView("login"); setResetDone(false); setResetEmail(""); }}>
                ← Back to login
              </button>

              <h1 className="greeting" style={{ fontSize: "1.9rem", marginBottom: "0.5rem" }}>
                Reset access
              </h1>
              <p className="subtext">Enter your email — your administrator will be notified.</p>

              {resetDone ? (
                <div className="reset-success">
                  ✓ Your administrator has been notified.<br/>
                  Contact them directly for new credentials.
                </div>
              ) : (
                <form onSubmit={handleReset}>
                  <div className="field-group">
                    <div>
                      <label className="field-label">Email</label>
                      <input
                        className="field-input"
                        type="email"
                        placeholder="you@ems.gov.in"
                        value={resetEmail}
                        onChange={e => setResetEmail(e.target.value)}
                      />
                    </div>
                  </div>
                  <button className="btn-login" type="submit" disabled={loading || !resetEmail}>
                    {loading ? "Sending…" : "Notify Admin →"}
                  </button>
                </form>
              )}
            </>
          )}

          <div className="footer-note">
            <span>EMS Dispatch v2.0</span>
            <span>Uttarakhand Response Network</span>
          </div>
        </div>
      </div>
    </>
  );
}
