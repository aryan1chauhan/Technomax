/**
 * Result.jsx — Enriched dispatch result page.
 *
 * Consumes the new DispatchResponse shape:
 *   selected_hospital  { score, score_breakdown, explanation, pros, cons, ... }
 *   alternatives       [ ScoredHospitalResponse, ... ]
 *   rejected_hospitals { missing_equipment, insufficient_beds, too_far, total_rejected }
 *   no_match           bool
 *   no_match_reason    string
 *   fallback_options   string[]
 *   triage             { condition, severity, required_equipment }
 *
 * Legacy flat fields (hospital_id, hospital_name, distance_km, etc.) are still
 * present in the response and used for map navigation — no Map.jsx changes needed.
 */

import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import CaseTimeline from "../components/CaseTimeline";

// ── Severity badge config (mirrors backend severity.py) ──────────────────────
const SEVERITY_BADGE = {
  critical: { label: "CRITICAL", bg: "#7f1d1d", text: "#fecaca", border: "#ef4444", dot: "#f87171" },
  moderate: { label: "MODERATE", bg: "#78350f", text: "#fef3c7", border: "#f59e0b", dot: "#fbbf24" },
  low:      { label: "LOW",      bg: "#14532d", text: "#dcfce7", border: "#22c55e", dot: "#4ade80" },
};

// ── Sub-score color bands ────────────────────────────────────────────────────
function scoreColor(v) {
  if (v >= 0.75) return "#4ade80";
  if (v >= 0.50) return "#fbbf24";
  if (v >= 0.25) return "#f97316";
  return "#f87171";
}

// ── Score ring (SVG arc) ─────────────────────────────────────────────────────
function ScoreRing({ value, size = 72, label }) {
  const r = (size - 8) / 2;
  const circ = 2 * Math.PI * r;
  const filled = circ * value;
  const color = scoreColor(value);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1e293b" strokeWidth={7} />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none"
          stroke={color}
          strokeWidth={7}
          strokeDasharray={`${filled} ${circ - filled}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)" }}
        />
        <text
          x={size / 2} y={size / 2 + 1}
          textAnchor="middle" dominantBaseline="middle"
          style={{
            fill: color, fontSize: size * 0.22, fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 700, transform: "rotate(90deg)",
            transformOrigin: `${size / 2}px ${size / 2}px`,
          }}
        >
          {Math.round(value * 100)}
        </text>
      </svg>
      <span style={{ fontSize: 10, color: "#64748b", textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "monospace" }}>
        {label}
      </span>
    </div>
  );
}

// ── Chip ─────────────────────────────────────────────────────────────────────
function Chip({ text, positive }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "3px 10px", borderRadius: 20,
      fontSize: 12, fontWeight: 500,
      background: positive ? "rgba(74,222,128,0.08)" : "rgba(248,113,113,0.08)",
      border: `1px solid ${positive ? "rgba(74,222,128,0.25)" : "rgba(248,113,113,0.25)"}`,
      color: positive ? "#86efac" : "#fca5a5",
    }}>
      <span style={{ fontSize: 8 }}>{positive ? "▲" : "▼"}</span>
      {text}
    </span>
  );
}

// ── Alternative hospital card ──────
function AlternativeCard({ hospital, onOverride, index }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div style={{
      background: "rgba(15,23,42,0.6)", border: "1px solid #1e293b",
      borderRadius: 10, padding: "14px 16px",
      display: "flex", flexDirection: "column", gap: 8,
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <span style={{ fontSize: 11, color: "#475569", marginRight: 8 }}>ALT {index + 1}</span>
          <span style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 14 }}>{hospital.name}</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 13, color: scoreColor(hospital.score), fontFamily: "monospace", fontWeight: 700 }}>
            {Math.round(hospital.score * 100)}
          </span>
          <button
            onClick={() => setExpanded(e => !e)}
            style={{ background: "none", border: "none", color: "#475569", cursor: "pointer", fontSize: 12 }}
          >
            {expanded ? "▲" : "▼"}
          </button>
          <button
            onClick={() => onOverride(hospital)}
            style={{
              padding: "4px 12px", borderRadius: 6, fontSize: 11, fontWeight: 600,
              background: "rgba(251,191,36,0.1)", border: "1px solid rgba(251,191,36,0.3)",
              color: "#fbbf24", cursor: "pointer",
            }}
          >
            OVERRIDE →
          </button>
        </div>
      </div>
      <div style={{ display: "flex", gap: 16, fontSize: 12, color: "#64748b" }}>
        <span>📍 {hospital.distance_km} km</span>
        <span>🛏 {hospital.available_beds} beds</span>
        <span>⏱ {hospital.eta_minutes} min</span>
      </div>
      {expanded && (
        <div style={{ borderTop: "1px solid #1e293b", paddingTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {hospital.pros?.map((p, i) => <Chip key={i} text={p} positive />)}
            {hospital.cons?.map((c, i) => <Chip key={i} text={c} positive={false} />)}
          </div>
          <div style={{ fontSize: 11, color: "#475569" }}>
            {hospital.explanation?.join(" ")}
          </div>
        </div>
      )}
    </div>
  );
}

// ── No-match state ────────────────────────────────────────────────────────────
function NoMatchView({ result, onNewDispatch }) {
  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "40px 20px", fontFamily: "system-ui, sans-serif" }}>
      <div style={{
        background: "rgba(127,29,29,0.15)", border: "1px solid rgba(239,68,68,0.3)",
        borderRadius: 12, padding: 24, textAlign: "center", marginBottom: 24,
      }}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
        <div style={{ color: "#fca5a5", fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
          No Eligible Hospital Found
        </div>
        <div style={{ color: "#94a3b8", fontSize: 13, lineHeight: 1.6 }}>
          {result.no_match_reason}
        </div>
      </div>

      {result.rejected_hospitals && (
        <div style={{
          background: "rgba(15,23,42,0.8)", border: "1px solid #1e293b",
          borderRadius: 10, padding: 16, marginBottom: 20,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
            Rejection Breakdown
          </div>
          {[
            ["Missing equipment", result.rejected_hospitals.missing_equipment],
            ["Insufficient beds", result.rejected_hospitals.insufficient_beds],
            ["Too far", result.rejected_hospitals.too_far],
          ].map(([label, count]) => count > 0 && (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #0f172a" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>{label}</span>
              <span style={{ color: "#f87171", fontFamily: "monospace", fontWeight: 700 }}>{count}</span>
            </div>
          ))}
        </div>
      )}

      {result.fallback_options?.length > 0 && (
        <div style={{
          background: "rgba(15,23,42,0.8)", border: "1px solid #1e293b",
          borderRadius: 10, padding: 16, marginBottom: 20,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
            Nearest Hospitals (Equipment Not Guaranteed)
          </div>
          {result.fallback_options.map((opt, i) => (
            <div key={i} style={{ color: "#94a3b8", fontSize: 13, padding: "5px 0", borderBottom: "1px solid #0f172a" }}>
              {opt}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onNewDispatch}
        style={{
          width: "100%", padding: "12px 0", borderRadius: 8, fontSize: 14,
          fontWeight: 700, background: "rgba(248,113,113,0.1)", border: "1px solid rgba(248,113,113,0.3)",
          color: "#f87171", cursor: "pointer",
        }}
      >
        ← NEW DISPATCH
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Result() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const result = state?.result;

  const [mounted, setMounted] = useState(false);
  useEffect(() => { setTimeout(() => setMounted(true), 50); }, []);

  if (!result) {
    return (
      <div style={{ padding: 40, color: "#94a3b8", textAlign: "center" }}>
        No dispatch result found.{" "}
        <button onClick={() => navigate("/dispatch")} style={{ color: "#60a5fa", background: "none", border: "none", cursor: "pointer" }}>
          Return to Dispatch
        </button>
      </div>
    );
  }

  if (result.no_match) {
    return <NoMatchView result={result} onNewDispatch={() => navigate("/dispatch")} />;
  }

  const sh = result.selected_hospital;
  const triage = result.triage || {};
  const severity = (triage.severity || "moderate").toLowerCase();
  const badge = SEVERITY_BADGE[severity] || SEVERITY_BADGE.moderate;
  const breakdown = sh?.score_breakdown || {};

  const handleOverride = (altHospital) => {
    navigate("/map", {
      state: {
        ...state,
        result: {
          ...result,
          hospital_id: altHospital.hospital_id,
          hospital_name: altHospital.name,
          distance_km: altHospital.distance_km,
          eta_minutes: altHospital.eta_minutes,
          hospital_lat: altHospital.hospital_lat,
          hospital_lng: altHospital.hospital_lng,
          address: altHospital.address,
          selected_hospital: altHospital,
          overridden: true,
        },
      },
    });
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "#060d1a",
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
      color: "#e2e8f0",
    }}>
      {/* ── Top bar ── */}
      <div style={{
        borderBottom: "1px solid #0f172a",
        padding: "12px 24px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "rgba(6,13,26,0.95)",
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#f87171", fontSize: 16 }}>🚑</span>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", color: "#94a3b8" }}>
            MEDIROUTE / DISPATCH RESULT
          </span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => navigate("/map", { state })}
            style={{
              padding: "6px 16px", borderRadius: 6, fontSize: 11, fontWeight: 700,
              background: "rgba(96,165,250,0.1)", border: "1px solid rgba(96,165,250,0.25)",
              color: "#60a5fa", cursor: "pointer", letterSpacing: "0.08em",
            }}
          >
            VIEW MAP →
          </button>
          <button
            onClick={() => navigate("/dispatch")}
            style={{
              padding: "6px 16px", borderRadius: 6, fontSize: 11, fontWeight: 700,
              background: "rgba(100,116,139,0.1)", border: "1px solid #1e293b",
              color: "#64748b", cursor: "pointer", letterSpacing: "0.08em",
            }}
          >
            NEW DISPATCH
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "28px 20px" }}>

        {/* ── Severity + hospital header ── */}
        <div style={{
          opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.4s ease",
          background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
          borderRadius: 14, padding: "20px 24px", marginBottom: 20,
          display: "flex", justifyContent: "space-between", alignItems: "flex-start",
          flexWrap: "wrap", gap: 16,
        }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
              <span style={{
                padding: "3px 12px", borderRadius: 20, fontSize: 11, fontWeight: 800,
                letterSpacing: "0.1em",
                background: badge.bg, color: badge.text, border: `1px solid ${badge.border}`,
              }}>
                {badge.label}
              </span>
              <span style={{ color: "#475569", fontSize: 12 }}>{triage.condition}</span>
            </div>
            <div style={{ fontSize: 22, fontWeight: 800, color: "#f1f5f9", marginBottom: 4 }}>
              {sh?.name}
            </div>
            <div style={{ fontSize: 12, color: "#475569" }}>{sh?.address || "Address not available"}</div>
          </div>
          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#60a5fa" }}>{sh?.distance_km} km</div>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.08em" }}>DISTANCE</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#34d399" }}>{sh?.eta_minutes} min</div>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.08em" }}>ETA</div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 22, fontWeight: 800, color: "#a78bfa" }}>{sh?.available_beds}</div>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.08em" }}>BEDS</div>
            </div>
          </div>
        </div>

        {/* ── Score breakdown rings ── */}
        <div style={{
          opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.5s ease 0.1s",
          background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
          borderRadius: 14, padding: "20px 24px", marginBottom: 20,
        }}>
          <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 16, textTransform: "uppercase" }}>
            Score Breakdown
          </div>
          <div style={{ display: "flex", justifyContent: "space-around", flexWrap: "wrap", gap: 16 }}>
            <ScoreRing value={breakdown.distance  ?? 0} label="Distance"   />
            <ScoreRing value={breakdown.beds       ?? 0} label="Capacity"   />
            <ScoreRing value={breakdown.specialist ?? 0} label="Specialist" />
            <ScoreRing value={breakdown.equipment  ?? 1} label="Equipment"  />
            <ScoreRing value={sh?.score ?? 0} size={88}  label="Overall"    />
          </div>
        </div>

        {/* ── Explanation + pros/cons ── */}
        <div style={{
          opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.5s ease 0.18s",
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20,
        }}>
          {/* Explanation */}
          <div style={{
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px",
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase" }}>
              Reasoning
            </div>
            {(sh?.explanation || []).map((line, i) => (
              <div key={i} style={{
                fontSize: 12, color: "#94a3b8", lineHeight: 1.7,
                paddingBottom: 6, borderBottom: i < (sh.explanation.length - 1) ? "1px solid #0f172a" : "none",
                marginBottom: 6,
              }}>
                {line}
              </div>
            ))}
          </div>

          {/* Pros / Cons */}
          <div style={{
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px",
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase" }}>
              Pros / Cons
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(sh?.pros || []).map((p, i) => <Chip key={`p-${i}`} text={p} positive />)}
              {(sh?.cons || []).map((c, i) => <Chip key={`c-${i}`} text={c} positive={false} />)}
            </div>
          </div>
        </div>

        {/* ── Alternatives ── */}
        {result.alternatives?.length > 0 && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.26s",
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px", marginBottom: 20,
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 14, textTransform: "uppercase" }}>
              Alternative Hospitals
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {result.alternatives.map((alt, i) => (
                <AlternativeCard
                  key={alt.hospital_id}
                  hospital={alt}
                  index={i}
                  onOverride={handleOverride}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Rejection stats ── */}
        {result.rejected_hospitals?.total_rejected > 0 && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.32s",
            background: "rgba(15,23,42,0.5)", border: "1px solid #0f172a",
            borderRadius: 10, padding: "12px 18px", marginBottom: 20,
            display: "flex", gap: 24, flexWrap: "wrap",
          }}>
            <div style={{ fontSize: 10, color: "#334155", letterSpacing: "0.1em", textTransform: "uppercase", alignSelf: "center" }}>
              Filtered out:
            </div>
            {result.rejected_hospitals.missing_equipment > 0 && (
              <span style={{ fontSize: 12, color: "#475569" }}>
                <span style={{ color: "#f87171", fontWeight: 700 }}>{result.rejected_hospitals.missing_equipment}</span> missing equipment
              </span>
            )}
            {result.rejected_hospitals.insufficient_beds > 0 && (
              <span style={{ fontSize: 12, color: "#475569" }}>
                <span style={{ color: "#f87171", fontWeight: 700 }}>{result.rejected_hospitals.insufficient_beds}</span> insufficient beds
              </span>
            )}
            {result.rejected_hospitals.too_far > 0 && (
              <span style={{ fontSize: 12, color: "#475569" }}>
                <span style={{ color: "#f87171", fontWeight: 700 }}>{result.rejected_hospitals.too_far}</span> too far
              </span>
            )}
            <span style={{ fontSize: 12, color: "#334155", marginLeft: "auto" }}>
              {result.rejected_hospitals.total_evaluated} evaluated
            </span>
          </div>
        )}

        {/* ── Case timeline ── */}
        {result.case_id && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.38s",
          }}>
            <CaseTimeline caseId={result.case_id} />
          </div>
        )}

        {/* ── Data source footer ── */}
        <div style={{
          marginTop: 20, padding: "10px 0",
          borderTop: "1px solid #0f172a",
          display: "flex", justifyContent: "space-between",
          fontSize: 10, color: "#334155",
        }}>
          <span>DATA SOURCE: {sh?.data_source?.toUpperCase() || "LIVE"}</span>
          <span>LAST UPDATED: {sh?.last_updated ? new Date(sh.last_updated).toLocaleTimeString() : "—"}</span>
        </div>
      </div>
    </div>
  );
}
