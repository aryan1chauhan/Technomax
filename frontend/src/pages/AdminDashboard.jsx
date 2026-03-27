import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

const GREEN = "#00ff41";
const DIM = "#00aa2a";
const DARK = "#006600";
const RED = "#ff4444";
const YELLOW = "#ffff00";
const BG = "#0a0a0a";
const MONO = "'Courier New', 'Lucida Console', monospace";

// ASCII bar chart — fills `width` chars proportionally
function AsciiBar({ value, max, width = 18, color = GREEN }) {
  const filled = max > 0 ? Math.round((value / max) * width) : 0;
  const empty = width - filled;
  return (
    <span style={{ color }}>
      {"█".repeat(filled)}{"░".repeat(empty)}
    </span>
  );
}

function StatBox({ label, value, sub, color = GREEN }) {
  return (
    <div style={{
      border: `1px solid ${DARK}`,
      padding: "12px 16px",
      minWidth: 140,
      flex: 1,
    }}>
      <div style={{ color: DARK, fontSize: 10, letterSpacing: 2, marginBottom: 4 }}>
        {label}
      </div>
      <div style={{ color, fontSize: 28, fontWeight: "bold", lineHeight: 1 }}>
        {value}
      </div>
      {sub && (
        <div style={{ color: DARK, fontSize: 10, marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [time, setTime] = useState(new Date());
  const [blink, setBlink] = useState(true);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    const b = setInterval(() => setBlink((v) => !v), 500);
    return () => { clearInterval(t); clearInterval(b); };
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("/api/cases/admin/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || "Failed to fetch stats");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const t = setInterval(fetchStats, 15000); // refresh every 15s
    return () => clearInterval(t);
  }, []);

  const maxBeds = data
    ? Math.max(...(data.districts?.map((d) => d.beds) || [1]))
    : 1;

  return (
    <div style={{ minHeight: "100vh", background: BG, fontFamily: MONO, padding: "1rem", position: "relative" }}>
      {/* Scanlines */}
      <div style={{
        position: "fixed", inset: 0,
        background: "repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,65,0.015) 2px,rgba(0,255,65,0.015) 4px)",
        pointerEvents: "none", zIndex: 1,
      }} />

      <div style={{ maxWidth: 960, margin: "0 auto", position: "relative", zIndex: 2 }}>

        {/* ── Header ── */}
        <div style={{ marginBottom: "1.5rem" }}>
          <div style={{ color: DARK, fontSize: 12 }}>
            ╔══════════════════════════════════════════════════════════════╗
          </div>
          <div style={{ color: GREEN, fontSize: 14, fontWeight: "bold" }}>
            ║&nbsp;&nbsp;⚡ MEDIROUTE — SYSTEM CONTROL PANEL &nbsp;•&nbsp;
            <span style={{ color: DIM }}>ADMIN</span>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;║
          </div>
          <div style={{ color: DARK, fontSize: 12 }}>
            ╚══════════════════════════════════════════════════════════════╝
          </div>
          <div style={{ color: DARK, fontSize: 11, marginTop: 6, display: "flex", justifyContent: "space-between" }}>
            <span>
              {time.toLocaleDateString("en-IN")} &nbsp;
              {time.toLocaleTimeString()} IST
            </span>
            <span style={{ color: data ? GREEN : YELLOW }}>
              {data ? `● LIVE — auto-refresh 15s` : blink ? "● CONNECTING..." : "○ CONNECTING..."}
            </span>
          </div>
        </div>

        {loading && (
          <div style={{ color: DIM, fontSize: 13, textAlign: "center", padding: "4rem" }}>
            LOADING SYSTEM DATA{blink ? "..." : "   "}
          </div>
        )}

        {error && (
          <div style={{ color: RED, fontSize: 13, padding: "1rem", border: `1px solid ${RED}` }}>
            ⚠ ERROR: {error}
          </div>
        )}

        {data && (
          <>
            {/* ── Stat Cards ── */}
            <div style={{ marginBottom: "1.5rem" }}>
              <div style={{ color: DARK, fontSize: 11, marginBottom: 8 }}>
                ┌─── SYSTEM OVERVIEW ──────────────────────────────────────────┐
              </div>
              <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                <StatBox
                  label="HOSPITALS ONLINE"
                  value={data.total_hospitals}
                  sub={`${data.accepting_hospitals} currently accepting`}
                />
                <StatBox
                  label="TOTAL BEDS"
                  value={data.total_beds.toLocaleString()}
                  sub="across Uttarakhand"
                  color={DIM}
                />
                <StatBox
                  label="ICU BEDS"
                  value={data.total_icu.toLocaleString()}
                  sub="critical care capacity"
                  color={YELLOW}
                />
                <StatBox
                  label="TOTAL DISPATCHES"
                  value={data.total_cases}
                  sub={`${data.cases_last_24h} in last 24h`}
                  color={GREEN}
                />
              </div>
              <div style={{ color: DARK, fontSize: 11, marginTop: 8 }}>
                └──────────────────────────────────────────────────────────────┘
              </div>
            </div>

            {/* ── District Breakdown ── */}
            <div style={{ marginBottom: "1.5rem" }}>
              <div style={{ color: DARK, fontSize: 11, marginBottom: 8 }}>
                ┌─── DISTRICT CAPACITY MAP ────────────────────────────────────┐
              </div>
              <div style={{ padding: "0 1rem" }}>
                {/* Column headers */}
                <div style={{ display: "grid", gridTemplateColumns: "110px 1fr 60px 60px 70px", gap: 8, marginBottom: 6 }}>
                  <span style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>DISTRICT</span>
                  <span style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>BED CAPACITY</span>
                  <span style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>BEDS</span>
                  <span style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>ICU</span>
                  <span style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>HOSP.</span>
                </div>
                {data.districts.map((d) => (
                  <div
                    key={d.name}
                    style={{
                      display: "grid",
                      gridTemplateColumns: "110px 1fr 60px 60px 70px",
                      gap: 8,
                      alignItems: "center",
                      marginBottom: 8,
                      padding: "6px 0",
                      borderBottom: "1px solid #0d1f0d",
                    }}
                  >
                    <span style={{ color: GREEN, fontSize: 12 }}>{d.name.toUpperCase()}</span>
                    <span>
                      <AsciiBar value={d.beds} max={maxBeds} width={22} />
                    </span>
                    <span style={{ color: DIM, fontSize: 12 }}>{d.beds}</span>
                    <span style={{ color: YELLOW, fontSize: 12 }}>{d.icu}</span>
                    <span style={{ color: DARK, fontSize: 12 }}>
                      {d.accepting}/{d.hospitals}
                    </span>
                  </div>
                ))}
              </div>
              <div style={{ color: DARK, fontSize: 11, marginTop: 4 }}>
                └──────────────────────────────────────────────────────────────┘
              </div>
            </div>

            {/* ── Recent Dispatches ── */}
            <div style={{ marginBottom: "1.5rem" }}>
              <div style={{ color: DARK, fontSize: 11, marginBottom: 8 }}>
                ┌─── RECENT DISPATCHES (last 24h) ─────────────────────────────┐
              </div>
              {data.recent_cases.length === 0 ? (
                <div style={{ color: DARK, fontSize: 12, padding: "1rem" }}>
                  NO DISPATCHES IN LAST 24 HOURS
                </div>
              ) : (
                <div style={{ padding: "0 0.5rem" }}>
                  {/* Header row */}
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "60px 130px 220px 80px 80px 70px",
                    gap: 8, marginBottom: 6,
                  }}>
                    {["ID", "TIME", "HOSPITAL", "CONDITION", "ML SCORE", "DIST/ETA"].map((h) => (
                      <span key={h} style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>{h}</span>
                    ))}
                  </div>
                  {data.recent_cases.map((c) => {
                    const scoreColor = c.score > 0.7 ? GREEN : c.score > 0.4 ? YELLOW : RED;
                    return (
                      <div
                        key={c.id}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "60px 130px 220px 80px 80px 70px",
                          gap: 8,
                          padding: "5px 0",
                          borderBottom: "1px solid #0d1f0d",
                          fontSize: 11,
                          alignItems: "center",
                        }}
                      >
                        <span style={{ color: DARK }}>#{c.id}</span>
                        <span style={{ color: DARK }}>{c.created_at}</span>
                        <span style={{ color: DIM, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {c.hospital_name}
                        </span>
                        <span style={{ color: GREEN, textTransform: "uppercase" }}>
                          {c.condition?.replace("_", " ")}
                        </span>
                        <span style={{ color: scoreColor }}>
                          {(c.score * 100).toFixed(1)}%
                        </span>
                        <span style={{ color: DARK }}>
                          {c.distance_km}km/{c.eta_minutes}m
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
              <div style={{ color: DARK, fontSize: 11, marginTop: 8 }}>
                └──────────────────────────────────────────────────────────────┘
              </div>
            </div>

            {/* ── ML Model Status ── */}
            <div style={{ marginBottom: "1.5rem" }}>
              <div style={{ color: DARK, fontSize: 11, marginBottom: 8 }}>
                ┌─── ML ENGINE STATUS ─────────────────────────────────────────┐
              </div>
              <div style={{ padding: "0.5rem 1rem", display: "flex", flexWrap: "wrap", gap: 24 }}>
                {[
                  ["ALGORITHM",    "RandomForest (class_weight=balanced)"],
                  ["TRAINING SAMPLES", "112,800"],
                  ["FEATURES",     "15"],
                  ["HOSPITALS",    "188 (Uttarakhand)"],
                  ["THRESHOLD",    "Auto-tuned (F1 optimal)"],
                  ["FALLBACK",     "Rule-based scorer"],
                ].map(([k, v]) => (
                  <div key={k} style={{ minWidth: 200 }}>
                    <div style={{ color: DARK, fontSize: 10, letterSpacing: 1 }}>{k}</div>
                    <div style={{ color: GREEN, fontSize: 12 }}>{v}</div>
                  </div>
                ))}
              </div>
              <div style={{ color: DARK, fontSize: 11, marginTop: 4 }}>
                └──────────────────────────────────────────────────────────────┘
              </div>
            </div>

          </>
        )}

        {/* ── Nav ── */}
        <div style={{ display: "flex", gap: 10, marginTop: "1rem" }}>
          <button
            onClick={() => navigate("/dispatch")}
            style={{ background: "transparent", border: `1px solid ${DARK}`, color: DARK, fontFamily: MONO, fontSize: 11, padding: "8px 16px", cursor: "pointer" }}
          >
            [ DISPATCH CONSOLE ]
          </button>
          <button
            onClick={() => { localStorage.clear(); navigate("/login"); }}
            style={{ background: "transparent", border: `1px solid #330000`, color: "#660000", fontFamily: MONO, fontSize: 11, padding: "8px 16px", cursor: "pointer" }}
          >
            [ LOGOUT ]
          </button>
        </div>

        <div style={{ color: "#111", fontSize: 10, textAlign: "center", marginTop: "2rem", letterSpacing: 1 }}>
          MEDIROUTE CONTROL SYSTEM • UTTARAKHAND STATE EMERGENCY NETWORK
        </div>
      </div>
    </div>
  );
}
