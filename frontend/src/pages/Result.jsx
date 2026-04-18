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

// ── Constraint failure reason humanizer ─────────────────────────────────────
const NO_MATCH_REASON_LABELS = {
  no_viable_hospital_after_constraints: "No hospital met all required criteria",
  missing_critical_equipment:           "No hospital has the required equipment",
  eta_too_high:                         "All hospitals are too far for safe transport",
  survival_below_threshold:             "Patient condition too critical for available options",
  corrupted_input_detected:             "Dispatch data could not be verified",
  no_hospitals_available:               "No hospitals are currently in the system",
};

function humanizeReason(raw) {
  if (!raw) return "No viable hospital found";
  return NO_MATCH_REASON_LABELS[raw] ?? "No viable hospital found";
}

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
  const rawReason = result.no_match_reason || result.failure_reason || "";
  const humanReason = humanizeReason(rawReason);
  // Detect hard-constraint failures vs soft no-match
  const isConstraintFailure = rawReason in NO_MATCH_REASON_LABELS;
  const rh = result.rejected_hospitals;

  return (
    <div style={{ maxWidth: 640, margin: "0 auto", padding: "40px 20px", fontFamily: "system-ui, sans-serif" }}>
      <div style={{
        background: "rgba(127,29,29,0.15)", border: "1px solid rgba(239,68,68,0.3)",
        borderRadius: 12, padding: 24, textAlign: "center", marginBottom: 24,
      }}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>{isConstraintFailure ? "🚫" : "⚠️"}</div>
        <div style={{ color: "#fca5a5", fontSize: 18, fontWeight: 700, marginBottom: 8 }}>
          No Eligible Hospital Found
        </div>
        {/* Human-readable reason — never raw snake_case */}
        <div style={{ color: "#94a3b8", fontSize: 13, lineHeight: 1.6, marginBottom: isConstraintFailure ? 10 : 0 }}>
          {humanReason}
        </div>
        {/* Constraint badge — shows the technical code discreetly for ops staff */}
        {isConstraintFailure && (
          <div style={{
            display: "inline-block", marginTop: 8,
            padding: "2px 10px", borderRadius: 20,
            fontSize: 10, fontFamily: "monospace", letterSpacing: "0.08em",
            background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
            color: "#f87171",
          }}>
            {rawReason}
          </div>
        )}
      </div>

      {/* Rejection breakdown — graceful when rejected_hospitals is absent */}
      {rh ? (
        <div style={{
          background: "rgba(15,23,42,0.8)", border: "1px solid #1e293b",
          borderRadius: 10, padding: 16, marginBottom: 20,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 12 }}>
            Rejection Breakdown
          </div>
          {[
            ["Missing equipment", rh.missing_equipment],
            ["Insufficient beds", rh.insufficient_beds],
            ["Too far",           rh.too_far],
          ].map(([label, count]) => (count ?? 0) > 0 && (
            <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "5px 0", borderBottom: "1px solid #0f172a" }}>
              <span style={{ color: "#94a3b8", fontSize: 13 }}>{label}</span>
              <span style={{ color: "#f87171", fontFamily: "monospace", fontWeight: 700 }}>{count}</span>
            </div>
          ))}
          {(rh.total_evaluated ?? 0) > 0 && (
            <div style={{ fontSize: 11, color: "#334155", marginTop: 8, textAlign: "right" }}>
              {rh.total_evaluated} hospitals evaluated
            </div>
          )}
        </div>
      ) : isConstraintFailure && (
        // Hard-constraint failure with no breakdown — show informational note
        <div style={{
          background: "rgba(15,23,42,0.6)", border: "1px solid #1e293b",
          borderRadius: 10, padding: "12px 16px", marginBottom: 20,
          fontSize: 12, color: "#64748b", lineHeight: 1.6,
        }}>
          All hospitals in range were evaluated and excluded by capability constraints.
          No trauma-capable facility was available at the time of dispatch.
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

  // Fix 3: null-guard — engine may return no_match:false but sh:null
  // when no_viable_hospital_after_constraints fires (hard-gated failure).
  // Synthesize a no-match view rather than rendering a blank header.
  if (!sh) {
    const syntheticResult = {
      ...result,
      no_match_reason: result.failure_reason || result.no_match_reason || "no_viable_hospital_after_constraints",
    };
    return <NoMatchView result={syntheticResult} onNewDispatch={() => navigate("/dispatch")} />;
  }
  const triage = result.triage || {};
  const severity = (triage.severity || "moderate").toLowerCase();
  const badge = SEVERITY_BADGE[severity] || SEVERITY_BADGE.moderate;
  const breakdown = sh?.score_breakdown || {};
  const decisionType = result.decision_type || triage.decision_type || "direct";
  const isStabilizeFirst = decisionType === "stabilize_first";
  const routePrimary = result.primary_destination || sh;
  const routeSecondary = result.secondary_destination;
  const routingReasoning = result.reasoning || {};
  const stabilityScore = Number(routingReasoning.stability_score || 0);
  const diversionReasons = [
    ...(routingReasoning.missing_equipment || []).map((item) => `Missing ambulance equipment: ${item}`),
    ...(routingReasoning.vitals_flags || []).map((flag) => `Critical vitals flag: ${flag.replaceAll("_", " ")}`),
  ];
  const diversionText = diversionReasons.length > 0
    ? diversionReasons.join("; ")
    : "Stability constraints required immediate stabilization before final transfer.";

  const destinationName = (destination) => destination?.name || destination?.hospital_name || "Unknown";
  const destinationEta = (destination) => destination?.eta_minutes ?? "-";
  const destinationDistance = (destination) => destination?.distance_km ?? "-";

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
      <div className="sticky top-0 z-50 flex justify-between items-center px-6 py-3 border-b border-[#0f172a] bg-[#060d1a]/80 backdrop-blur-md">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#f87171", fontSize: 16 }}>🚑</span>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", color: "#94a3b8" }}>
            MEDIROUTE / DISPATCH RESULT
          </span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => navigate("/map", { state })}
            className="px-4 py-1.5 rounded-md text-[11px] font-bold tracking-wider text-[#60a5fa] bg-blue-500/10 border border-blue-500/25 hover:bg-blue-500/20 transition-all flex items-center gap-1"
          >
            VIEW MAP →
          </button>
          <button
            onClick={() => navigate("/dispatch")}
            className="px-4 py-1.5 rounded-md text-[11px] font-bold tracking-wider text-[#94a3b8] bg-slate-500/10 border border-[#1e293b] hover:bg-slate-500/20 transition-all"
          >
            NEW DISPATCH
          </button>
        </div>
      </div>

      <div style={{ maxWidth: 800, margin: "0 auto", padding: "28px 20px" }}>

        {/* ── Severity + hospital header ── */}
        <div 
          className="flex justify-between items-start flex-wrap gap-4 mb-5 p-6 rounded-2xl border border-[#1e293b] bg-slate-900/50 backdrop-blur-sm shadow-xl"
          style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.4s ease",
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

        {/* ── Two-hop route (stabilize first only) ── */}
        {isStabilizeFirst && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.45s ease 0.06s",
            background: "rgba(15,23,42,0.7)", border: "1px solid #1e293b",
            borderRadius: 14, padding: "18px 20px", marginBottom: 20,
          }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase" }}>
              Two-Step Route
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div style={{ background: "rgba(10,15,30,0.6)", border: "1px solid #1e293b", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 11, color: "#fbbf24", marginBottom: 6, letterSpacing: "0.08em" }}>STEP 1: STABILIZATION HOSPITAL</div>
                <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: 4 }}>{destinationName(routePrimary)}</div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>ETA: {destinationEta(routePrimary)} min</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>Distance: {destinationDistance(routePrimary)} km</div>
              </div>
              <div style={{ background: "rgba(10,15,30,0.6)", border: "1px solid #1e293b", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 11, color: "#60a5fa", marginBottom: 6, letterSpacing: "0.08em" }}>STEP 2: FINAL HOSPITAL</div>
                <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: 4 }}>{destinationName(routeSecondary)}</div>
                <div style={{ fontSize: 12, color: "#94a3b8" }}>ETA: {destinationEta(routeSecondary)} min</div>
                <div style={{ fontSize: 12, color: "#64748b" }}>Distance: {destinationDistance(routeSecondary)} km</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap", fontSize: 12 }}>
              <span style={{ color: "#93c5fd" }}>
                Stability Score: <strong style={{ color: scoreColor(stabilityScore) }}>{Math.round(stabilityScore * 100)}%</strong>
              </span>
              <span style={{ color: "#fca5a5" }}>Reason for diversion: {diversionText}</span>
            </div>
          </div>
        )}

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
