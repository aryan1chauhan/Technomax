import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const BOOT_LINES = [
  "MEDIROUTE OS v2.1.0 — UTTARAKHAND EMERGENCY DISPATCH",
  "Initializing hospital network... [188 nodes online]",
  "Loading ML dispatch engine... [XGBoost/RF ready]",
  "WebSocket relay... [ACTIVE]",
  "GPS tracking module... [ACTIVE]",
  "System status: ALL SYSTEMS OPERATIONAL",
  "",
  "╔══════════════════════════════════════════════════╗",
  "║         AUTHORIZED PERSONNEL ONLY                ║",
  "║   Unauthorized access will be logged & reported  ║",
  "╚══════════════════════════════════════════════════╝",
  "",
  "Enter credentials to continue...",
];

// FIX #1: Decode role from JWT payload (backend doesn't return role in response body)
function getRoleFromToken(token) {
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    // Try common key names used in FastAPI JWT payloads
    return payload.role || payload.user_role || payload.sub_role || null;
  } catch {
    return null;
  }
}

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [bootLines, setBootLines] = useState([]);
  const [bootDone, setBootDone] = useState(false);
  const [blink, setBlink] = useState(true);

  // Boot sequence typewriter effect
  useEffect(() => {
    let i = 0;
    const interval = setInterval(() => {
      if (i < BOOT_LINES.length) {
        setBootLines((prev) => [...prev, BOOT_LINES[i]]);
        i++;
      } else {
        clearInterval(interval);
        setBootDone(true);
      }
    }, 120);
    return () => clearInterval(interval);
  }, []);

  // Cursor blink
  useEffect(() => {
    const t = setInterval(() => setBlink((b) => !b), 500);
    return () => clearInterval(t);
  }, []);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await axios.post("/api/auth/login", {
        email,
        password,
      });

      const { access_token } = res.data;
      localStorage.setItem("token", access_token);

      // FIX #1: Decode role from JWT payload since backend only returns access_token
      const role = getRoleFromToken(access_token);
      if (role) {
        localStorage.setItem("role", role);
      }

      if (role === "ambulance") navigate("/dispatch");
      else if (role === "hospital") navigate("/hospital/dashboard");
      else if (role === "admin") navigate("/admin/dashboard");
      else {
        // Fallback: if role can't be decoded, redirect based on email hint
        // or go to dispatch as safe default
        console.warn("Could not decode role from JWT. Defaulting to /dispatch.");
        navigate("/dispatch");
      }
    } catch {
      setError("ACCESS DENIED — Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.root}>
      {/* Scanline overlay */}
      <div style={styles.scanlines} />

      <div style={styles.container}>
        {/* Boot log */}
        <div style={styles.bootLog}>
          {bootLines.map((line, i) => (
            <div key={i} style={styles.bootLine}>
              {line.startsWith("MEDIROUTE") ? (
                <span style={styles.title}>{line}</span>
              ) : line.startsWith("╔") || line.startsWith("║") || line.startsWith("╚") ? (
                <span style={styles.border}>{line}</span>
              ) : line.startsWith("System status") ? (
                <span style={styles.success}>{line}</span>
              ) : line.startsWith("Enter") ? (
                <span style={styles.prompt}>{line}</span>
              ) : (
                <span style={styles.info}>{line}</span>
              )}
            </div>
          ))}
          {!bootDone && (
            <span style={styles.cursor}>{blink ? "█" : " "}</span>
          )}
        </div>

        {/* Login form — appears after boot */}
        {bootDone && (
          <div style={styles.formBox}>
            <div style={styles.formHeader}>
              ┌─── AUTHENTICATION REQUIRED ───────────────────┐
            </div>

            <form onSubmit={handleLogin} style={styles.form}>
              <div style={styles.field}>
                <label style={styles.label}>│  USER ID (EMAIL):</label>
                <div style={styles.inputRow}>
                  <span style={styles.prompt2}>&gt; </span>
                  <input
                    style={styles.input}
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoFocus
                    spellCheck={false}
                    placeholder="user@mediroute.in"
                  />
                </div>
              </div>

              <div style={styles.field}>
                <label style={styles.label}>│  PASSWORD:</label>
                <div style={styles.inputRow}>
                  <span style={styles.prompt2}>&gt; </span>
                  <input
                    style={styles.input}
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    placeholder="••••••••"
                  />
                </div>
              </div>

              {error && (
                <div style={styles.error}>
                  ⚠ {error}
                </div>
              )}

              <button
                type="submit"
                style={loading ? styles.btnLoading : styles.btn}
                disabled={loading}
              >
                {loading ? "[ AUTHENTICATING... ]" : "[ AUTHENTICATE → ]"}
              </button>
            </form>

            <div style={styles.formFooter}>
              └───────────────────────────────────────────────┘
            </div>

            <div style={styles.hint}>
              DEMO — amb1@test.com | bhagwati@test.com | pass: test123
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const GREEN = "#00ff41";
const DIM_GREEN = "#00aa2a";
const RED = "#ff4444";
const YELLOW = "#ffff00";
const BG = "#0a0a0a";
const MONO = "'Courier New', 'Lucida Console', monospace";

const styles = {
  root: {
    minHeight: "100vh",
    background: BG,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontFamily: MONO,
    position: "relative",
    overflow: "hidden",
  },
  scanlines: {
    position: "fixed",
    inset: 0,
    background:
      "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,255,65,0.015) 2px, rgba(0,255,65,0.015) 4px)",
    pointerEvents: "none",
    zIndex: 1,
  },
  container: {
    width: "min(720px, 96vw)",
    zIndex: 2,
    padding: "2rem 1rem",
  },
  bootLog: {
    marginBottom: "1.5rem",
    fontSize: "clamp(11px, 1.5vw, 13px)",
    lineHeight: "1.7",
  },
  bootLine: { display: "block" },
  title: { color: GREEN, fontWeight: "bold", fontSize: "1.1em" },
  border: { color: DIM_GREEN },
  success: { color: GREEN },
  info: { color: DIM_GREEN },
  prompt: { color: YELLOW },
  cursor: { color: GREEN, fontSize: "1rem" },
  formBox: { marginTop: "0.5rem" },
  formHeader: { color: DIM_GREEN, fontSize: "13px", marginBottom: "0.5rem" },
  form: { padding: "0 1rem" },
  field: { marginBottom: "1rem" },
  label: { color: DIM_GREEN, fontSize: "12px", display: "block", marginBottom: "4px" },
  inputRow: { display: "flex", alignItems: "center", gap: "6px" },
  prompt2: { color: GREEN, fontSize: "14px" },
  input: {
    background: "transparent",
    border: "none",
    borderBottom: `1px solid ${DIM_GREEN}`,
    color: GREEN,
    fontFamily: MONO,
    fontSize: "14px",
    outline: "none",
    width: "100%",
    padding: "4px 0",
    caretColor: GREEN,
  },
  error: {
    color: RED,
    fontSize: "13px",
    margin: "0.5rem 0",
    animation: "blink 1s step-end infinite",
  },
  btn: {
    marginTop: "1rem",
    background: "transparent",
    border: `1px solid ${GREEN}`,
    color: GREEN,
    fontFamily: MONO,
    fontSize: "14px",
    padding: "10px 24px",
    cursor: "pointer",
    letterSpacing: "2px",
    transition: "all 0.2s",
    width: "100%",
  },
  btnLoading: {
    marginTop: "1rem",
    background: "transparent",
    border: `1px solid ${DIM_GREEN}`,
    color: DIM_GREEN,
    fontFamily: MONO,
    fontSize: "14px",
    padding: "10px 24px",
    cursor: "not-allowed",
    letterSpacing: "2px",
    width: "100%",
  },
  formFooter: { color: DIM_GREEN, fontSize: "13px", marginTop: "0.5rem" },
  hint: {
    color: "#333",
    fontSize: "11px",
    marginTop: "1.5rem",
    textAlign: "center",
    letterSpacing: "1px",
  },
};
