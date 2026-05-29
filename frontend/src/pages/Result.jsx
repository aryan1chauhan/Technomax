/**
 * Result.jsx — Redesigned emergency medical dispatch UI.
 *
 * Fully conforms to the premium dark mode specifications:
 *   - Background: #0f172a
 *   - Cards: #1e293b
 *   - Borders: #334155
 *   - Monospace font for data values, clean sans-serif for labels and names.
 *   - Overall layout: single-column centered with max-width 900px.
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

// ── Dynamic Color-Coding Function ───────────────────────────────────────────
function scoreColor(v) {
  const pct = Math.round(v * 100);
  if (pct >= 80) return "#10b981"; // Green (80-100)
  if (pct >= 40) return "#f59e0b"; // Amber (40-79)
  return "#ef4444";                // Red (0-39)
}

// ── Custom Circular Score Ring Gauge ────────────────────────────────────────
function ScoreRing({ value, size = 80, label, isLarge = false }) {
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const filled = circ * value;
  const color = scoreColor(value);
  const pct = Math.round(value * 100);

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#334155" strokeWidth={isLarge ? 8 : 6} />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={isLarge ? 8 : 6}
            strokeDasharray={`${filled} ${circ - filled}`}
            strokeLinecap="round"
            style={{ transition: "stroke-dasharray 0.8s cubic-bezier(.4,0,.2,1)" }}
          />
        </svg>
        <div style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
          fontWeight: 700,
          fontSize: isLarge ? `${size * 0.26}px` : `${size * 0.24}px`,
          color: color,
        }}>
          {pct}
        </div>
      </div>
      <span style={{
        fontSize: "10px",
        color: "#94a3b8",
        textTransform: "uppercase",
        letterSpacing: "0.1em",
        fontFamily: "Inter, system-ui, -apple-system, sans-serif",
        fontWeight: 600,
        textAlign: "center"
      }}>
        {label}
      </span>
    </div>
  );
}

// ── Chip ─────────────────────────────────────────────────────────────────────
function Chip({ text, positive }) {
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 5,
      padding: "4px 10px",
      borderRadius: 20,
      fontSize: 11,
      fontWeight: 600,
      background: positive ? "rgba(16, 185, 129, 0.08)" : "rgba(239, 68, 68, 0.08)",
      border: `1px solid ${positive ? "rgba(16, 185, 129, 0.2)" : "rgba(239, 68, 68, 0.2)"}`,
      color: positive ? "#34d399" : "#fca5a5",
      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
    }}>
      <span style={{ fontSize: 8 }}>{positive ? "▲" : "▼"}</span>
      {text}
    </span>
  );
}

// ── Alternative Hospital Row Component ──────────────────────────────────────
function AlternativeRow({ hospital, onOverride, index }) {
  const [hovered, setHovered] = useState(false);
  const scorePercent = Math.round(hospital.score * 100);
  const badgeColor = scoreColor(hospital.score);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: hovered ? "rgba(30, 41, 59, 0.9)" : "#1e293b",
        border: "1px solid #334155",
        borderRadius: "12px",
        padding: "16px 20px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
        transition: "all 0.2s ease-in-out",
        boxShadow: hovered ? "0 4px 20px rgba(0, 0, 0, 0.25)" : "none",
        transform: hovered ? "translateY(-1px)" : "none",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        {/* Left side: Rank badge + Hospital Name */}
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{
            fontSize: "10px",
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
            fontWeight: "700",
            color: "#64748b",
            background: "rgba(100, 116, 139, 0.15)",
            border: "1px solid rgba(100, 116, 139, 0.25)",
            padding: "2px 8px",
            borderRadius: "4px",
            textTransform: "uppercase",
          }}>
            ALT {index + 1}
          </span>
          <span style={{
            fontFamily: "Inter, system-ui, -apple-system, sans-serif",
            fontWeight: "700",
            color: "#f1f5f9",
            fontSize: "15px",
          }}>
            {hospital.name}
          </span>
        </div>

        {/* Right side: Score badge + Override button */}
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
            fontWeight: "700",
            fontSize: "13px",
            color: badgeColor,
            background: `${badgeColor}15`,
            border: `1px solid ${badgeColor}30`,
            padding: "4px 10px",
            borderRadius: "6px",
          }}>
            {scorePercent}%
          </div>
          <button
            onClick={() => onOverride(hospital)}
            style={{
              padding: "6px 14px",
              borderRadius: "8px",
              fontSize: "11px",
              fontWeight: "700",
              background: hovered ? "#f59e0b" : "rgba(245, 158, 11, 0.1)",
              border: "1px solid rgba(245, 158, 11, 0.3)",
              color: hovered ? "#0f172a" : "#f59e0b",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            OVERRIDE
          </button>
        </div>
      </div>

      {/* Row Data pills */}
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
        {/* Distance pill */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: "rgba(148, 163, 184, 0.08)",
          border: "1px solid rgba(148, 163, 184, 0.15)",
          padding: "4px 10px",
          borderRadius: "16px",
          fontSize: "12px",
          color: "#cbd5e1",
        }}>
          <span>📍</span>
          <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: "600" }}>
            {hospital.distance_km} km
          </span>
        </div>

        {/* Bed pill */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: "rgba(148, 163, 184, 0.08)",
          border: "1px solid rgba(148, 163, 184, 0.15)",
          padding: "4px 10px",
          borderRadius: "16px",
          fontSize: "12px",
          color: "#cbd5e1",
        }}>
          <span>🛏</span>
          <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: "600" }}>
            {hospital.available_beds} beds
          </span>
        </div>

        {/* ETA pill */}
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          background: "rgba(148, 163, 184, 0.08)",
          border: "1px solid rgba(148, 163, 184, 0.15)",
          padding: "4px 10px",
          borderRadius: "16px",
          fontSize: "12px",
          color: "#cbd5e1",
        }}>
          <span>⏱</span>
          <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: "600" }}>
            {hospital.eta_minutes} min
          </span>
        </div>
      </div>
    </div>
  );
}

// ── No-Match View ────────────────────────────────────────────────────────────
function NoMatchView({ result, onNewDispatch }) {
  const rawReason = result.no_match_reason || result.failure_reason || "";
  const humanReason = humanizeReason(rawReason);
  const isConstraintFailure = rawReason in NO_MATCH_REASON_LABELS;
  const rh = result.rejected_hospitals;

  return (
    <div style={{
      maxWidth: 900,
      margin: "0 auto",
      padding: "40px 20px",
      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      color: "#cbd5e1",
    }}>
      <div style={{
        background: "#1e293b",
        border: "1px solid #334155",
        borderRadius: 16,
        padding: 32,
        textAlign: "center",
        marginBottom: 24,
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.2)",
      }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>{isConstraintFailure ? "🚫" : "⚠️"}</div>
        <div style={{ color: "#f87171", fontSize: 20, fontWeight: 800, marginBottom: 12 }}>
          No Eligible Hospital Found
        </div>
        <div style={{ color: "#94a3b8", fontSize: 14, lineHeight: 1.6, marginBottom: isConstraintFailure ? 16 : 0 }}>
          {humanReason}
        </div>
        {isConstraintFailure && (
          <div style={{
            display: "inline-block",
            marginTop: 12,
            padding: "4px 12px",
            borderRadius: 20,
            fontSize: 11,
            fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
            background: "rgba(239,68,68,0.08)",
            border: "1px solid rgba(239,68,68,0.2)",
            color: "#f87171",
          }}>
            {rawReason}
          </div>
        )}
      </div>

      {rh ? (
        <div style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: 16,
          padding: 24,
          marginBottom: 24,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16, fontWeight: "bold" }}>
            Rejection Breakdown
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[
              ["Missing equipment", rh.missing_equipment],
              ["Insufficient beds", rh.insufficient_beds],
              ["Too far",           rh.too_far],
            ].map(([label, count]) => (count ?? 0) > 0 && (
              <div key={label} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid #334155" }}>
                <span style={{ color: "#94a3b8", fontSize: 14 }}>{label}</span>
                <span style={{ color: "#f87171", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: 700 }}>{count}</span>
              </div>
            ))}
          </div>
          {(rh.total_evaluated ?? 0) > 0 && (
            <div style={{ fontSize: 11, color: "#475569", marginTop: 12, textAlign: "right", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>
              {rh.total_evaluated} hospitals evaluated
            </div>
          )}
        </div>
      ) : isConstraintFailure && (
        <div style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: 16,
          padding: "16px 20px",
          marginBottom: 24,
          fontSize: 13,
          color: "#94a3b8",
          lineHeight: 1.6,
        }}>
          All hospitals in range were evaluated and excluded by capability constraints.
          No trauma-capable facility was available at the time of dispatch.
        </div>
      )}

      {result.fallback_options?.length > 0 && (
        <div style={{
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: 16,
          padding: 24,
          marginBottom: 24,
        }}>
          <div style={{ color: "#64748b", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 16, fontWeight: "bold" }}>
            Nearest Hospitals (Equipment Not Guaranteed)
          </div>
          {result.fallback_options.map((opt, i) => (
            <div key={i} style={{ color: "#cbd5e1", fontSize: 14, padding: "8px 0", borderBottom: "1px solid #334155" }}>
              {opt}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onNewDispatch}
        style={{
          width: "100%",
          padding: "14px 0",
          borderRadius: 10,
          fontSize: 14,
          fontWeight: 700,
          background: "rgba(239, 68, 68, 0.1)",
          border: "1px solid rgba(239, 68, 68, 0.3)",
          color: "#f87171",
          cursor: "pointer",
          transition: "all 0.2s ease",
        }}
      >
        ← NEW DISPATCH
      </button>
    </div>
  );
}

// ── Main Page Component ──────────────────────────────────────────────────────
export default function Result() {
  const { state } = useLocation();
  const navigate = useNavigate();
  const result = state?.result;

  const [mounted, setMounted] = useState(false);
  useEffect(() => { setTimeout(() => setMounted(true), 50); }, []);

  if (!result) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "#0f172a",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#94a3b8",
        fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      }}>
        <div style={{ fontSize: 24, marginBottom: 12 }}>🚑</div>
        No dispatch result found.{" "}
        <button
          onClick={() => navigate("/dispatch")}
          style={{ color: "#38bdf8", background: "none", border: "none", cursor: "pointer", fontWeight: "bold", marginTop: 8 }}
        >
          Return to Dispatch
        </button>
      </div>
    );
  }

  if (result.no_match) {
    return (
      <div style={{ minHeight: "100vh", background: "#0f172a" }}>
        <NoMatchView result={result} onNewDispatch={() => navigate("/dispatch")} />
      </div>
    );
  }

  const sh = result.selected_hospital;

  if (!sh) {
    const syntheticResult = {
      ...result,
      no_match_reason: result.failure_reason || result.no_match_reason || "no_viable_hospital_after_constraints",
    };
    return (
      <div style={{ minHeight: "100vh", background: "#0f172a" }}>
        <NoMatchView result={syntheticResult} onNewDispatch={() => navigate("/dispatch")} />
      </div>
    );
  }

  const triage = result.triage || {};
  const severity = (triage.severity || "moderate").toLowerCase();

  // Mapped left border colors
  const severityColor =
    severity === "critical" ? "#ef4444" :
    severity === "moderate" ? "#fbbf24" : "#10b981";

  // Mapped badge styles
  const severityBg =
    severity === "critical" ? "rgba(239, 68, 68, 0.15)" :
    severity === "moderate" ? "rgba(251, 191, 36, 0.15)" : "rgba(16, 185, 129, 0.15)";
  const severityText =
    severity === "critical" ? "#fca5a5" :
    severity === "moderate" ? "#fbbf24" : "#86efac";
  const severityBorder =
    severity === "critical" ? "rgba(239, 68, 68, 0.3)" :
    severity === "moderate" ? "rgba(251, 191, 36, 0.3)" : "rgba(16, 185, 129, 0.3)";

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
      background: "#0f172a",
      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
      color: "#cbd5e1",
    }}>
      {/* ── Sticky Header bar ── */}
      <div style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "12px 24px",
        borderBottom: "1px solid #334155",
        background: "rgba(15, 23, 42, 0.85)",
        backdropFilter: "blur(8px)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ color: "#ef4444", fontSize: 16 }}>🚑</span>
          <span style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.12em", color: "#94a3b8" }}>
            MEDIROUTE / DISPATCH RESULT
          </span>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            onClick={() => navigate("/map", { state })}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              fontSize: "11px",
              fontWeight: "700",
              letterSpacing: "0.08em",
              color: "#60a5fa",
              background: "rgba(96, 165, 250, 0.1)",
              border: "1px solid rgba(96, 165, 250, 0.25)",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            VIEW MAP →
          </button>
          <button
            onClick={() => navigate("/dispatch")}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              fontSize: "11px",
              fontWeight: "700",
              letterSpacing: "0.08em",
              color: "#94a3b8",
              background: "#1e293b",
              border: "1px solid #334155",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            NEW DISPATCH
          </button>
        </div>
      </div>

      {/* Main Single Column Wrapper */}
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "28px 20px" }}>

        {/* ── TOP CARD: Primary Dispatch Result ── */}
        <div
          style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderLeft: `6px solid ${severityColor}`,
            borderRadius: "12px",
            padding: "24px",
            marginBottom: "24px",
            opacity: mounted ? 1 : 0,
            transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.4s ease",
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.25)",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {/* Severity Badge + Plain Text Condition */}
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <span style={{
                padding: "3px 12px",
                borderRadius: "16px",
                fontSize: "11px",
                fontWeight: "800",
                letterSpacing: "0.08em",
                background: severityBg,
                color: severityText,
                border: `1px solid ${severityBorder}`,
              }}>
                {severity.toUpperCase()}
              </span>
              <span style={{
                color: "#cbd5e1",
                fontSize: "14px",
                fontWeight: "500",
                textTransform: "lowercase",
              }}>
                {triage.condition}
              </span>
            </div>

            {/* Hospital Name (large & prominent) */}
            <h2 style={{
              fontSize: "26px",
              fontWeight: "800",
              color: "#f8fafc",
              margin: 0,
              letterSpacing: "-0.02em",
            }}>
              {sh?.name}
            </h2>

            {/* Address */}
            <p style={{
              fontSize: "13px",
              color: "#64748b",
              margin: "0 0 4px 0",
            }}>
              📍 {sh?.address || "Address not available"}
            </p>

            {/* Stat Pills in a Row */}
            <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginTop: "4px" }}>
              {/* Distance Pill */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "rgba(96, 165, 250, 0.08)",
                border: "1px solid rgba(96, 165, 250, 0.2)",
                padding: "6px 14px",
                borderRadius: "20px",
                fontSize: "13px",
                color: "#60a5fa",
              }}>
                <span>📍</span>
                <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: "700" }}>
                  {sh?.distance_km} km
                </span>
              </div>

              {/* ETA Pill */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "rgba(52, 211, 153, 0.08)",
                border: "1px solid rgba(52, 211, 153, 0.2)",
                padding: "6px 14px",
                borderRadius: "20px",
                fontSize: "13px",
                color: "#34d399",
              }}>
                <span>⏱</span>
                <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: "700" }}>
                  {sh?.eta_minutes} min
                </span>
              </div>

              {/* Beds Pill */}
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                background: "rgba(167, 139, 250, 0.08)",
                border: "1px solid rgba(167, 139, 250, 0.2)",
                padding: "6px 14px",
                borderRadius: "20px",
                fontSize: "13px",
                color: "#a78bfa",
              }}>
                <span>🛏</span>
                <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace", fontWeight: "700" }}>
                  {sh?.available_beds} beds
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* ── Two-hop route (stabilize first only) ── */}
        {isStabilizeFirst && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.45s ease 0.06s",
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 14, padding: "18px 20px", marginBottom: 20,
          }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase", fontWeight: "bold" }}>
              Two-Step Route
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
              <div style={{ background: "rgba(15,23,42,0.4)", border: "1px solid #334155", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 11, color: "#fbbf24", marginBottom: 6, letterSpacing: "0.08em", fontWeight: "bold" }}>STEP 1: STABILIZATION HOSPITAL</div>
                <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: 4, fontSize: "14px" }}>{destinationName(routePrimary)}</div>
                <div style={{ fontSize: 12, color: "#cbd5e1", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>ETA: {destinationEta(routePrimary)} min</div>
                <div style={{ fontSize: 12, color: "#cbd5e1", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>Distance: {destinationDistance(routePrimary)} km</div>
              </div>
              <div style={{ background: "rgba(15,23,42,0.4)", border: "1px solid #334155", borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: 11, color: "#60a5fa", marginBottom: 6, letterSpacing: "0.08em", fontWeight: "bold" }}>STEP 2: FINAL HOSPITAL</div>
                <div style={{ color: "#e2e8f0", fontWeight: 700, marginBottom: 4, fontSize: "14px" }}>{destinationName(routeSecondary)}</div>
                <div style={{ fontSize: 12, color: "#cbd5e1", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>ETA: {routeSecondary ? destinationEta(routeSecondary) : "-"} min</div>
                <div style={{ fontSize: 12, color: "#cbd5e1", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>Distance: {routeSecondary ? destinationDistance(routeSecondary) : "-"} km</div>
              </div>
            </div>
            <div style={{ display: "flex", gap: 20, flexWrap: "wrap", fontSize: 12 }}>
              <span style={{ color: "#cbd5e1" }}>
                Stability Score: <strong style={{ color: scoreColor(stabilityScore), fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>{Math.round(stabilityScore * 100)}%</strong>
              </span>
              <span style={{ color: "#fca5a5" }}>Reason for diversion: {diversionText}</span>
            </div>
          </div>
        )}

        {/* ── SCORE BREAKDOWN RINGS ── */}
        <div style={{
          opacity: mounted ? 1 : 0,
          transform: mounted ? "translateY(0)" : "translateY(12px)",
          transition: "all 0.5s ease 0.1s",
          background: "#1e293b",
          border: "1px solid #334155",
          borderRadius: 14,
          padding: "24px",
          marginBottom: "24px",
        }}>
          <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.12em", marginBottom: 20, textTransform: "uppercase", fontWeight: "bold" }}>
            Score Breakdown
          </div>
          
          {/* Top Row: 4 sub-gauges identical in size and style */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "16px", justifyItems: "center", width: "100%", marginBottom: "24px" }}>
            <ScoreRing value={breakdown.distance  ?? 0} label="Distance" size={80} />
            <ScoreRing value={breakdown.beds       ?? 0} label="Capacity" size={80} />
            <ScoreRing value={breakdown.specialist ?? 0} label="Specialist" size={80} />
            <ScoreRing value={breakdown.equipment  ?? 1} label="Equipment" size={80} />
          </div>

          {/* Bottom Row: Largest centered Overall match gauge */}
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", width: "100%" }}>
            <ScoreRing value={sh?.score ?? 0} label="Overall Match" size={110} isLarge />
            {(breakdown.ml_confidence ?? 0) > 0 && (
              <div style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginTop: 10,
                padding: "4px 12px",
                borderRadius: 16,
                background: "rgba(148, 163, 184, 0.06)",
                border: "1px solid rgba(148, 163, 184, 0.12)",
              }}>
                <span style={{
                  fontSize: 10,
                  color: "#64748b",
                  fontFamily: "Inter, system-ui, -apple-system, sans-serif",
                  fontWeight: 600,
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                }}>
                  ML Confidence
                </span>
                <span style={{
                  fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace",
                  fontWeight: 700,
                  fontSize: 12,
                  color: scoreColor(breakdown.ml_confidence),
                }}>
                  {Math.round(breakdown.ml_confidence * 100)}%
                </span>
              </div>
            )}
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
            background: "#1e293b", border: "1px solid #334155",
            borderRadius: 14, padding: "18px 20px",
          }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase", fontWeight: "bold" }}>
              Reasoning
            </div>
            {(sh?.explanation || []).map((line, i) => (
              <div key={i} style={{
                fontSize: 12, color: "#94a3b8", lineHeight: 1.7,
                paddingBottom: 6, borderBottom: i < (sh.explanation.length - 1) ? "1px solid #334155" : "none",
                marginBottom: 6,
              }}>
                {line}
              </div>
            ))}
          </div>

          {/* Pros / Cons */}
          <div style={{
            background: "#1e293b", border: "1px solid #334155",
            borderRadius: 14, padding: "18px 20px",
          }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.12em", marginBottom: 12, textTransform: "uppercase", fontWeight: "bold" }}>
              Pros / Cons
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(sh?.pros || []).map((p, i) => <Chip key={`p-${i}`} text={p} positive />)}
              {(sh?.cons || []).map((c, i) => <Chip key={`c-${i}`} text={c} positive={false} />)}
            </div>
          </div>
        </div>

        {/* ── ALTERNATIVE HOSPITALS ── */}
        {result.alternatives?.length > 0 && (
          <div style={{
            opacity: mounted ? 1 : 0, transform: mounted ? "translateY(0)" : "translateY(12px)",
            transition: "all 0.5s ease 0.26s",
            background: "#1e293b", border: "1px solid #334155",
            borderRadius: 14, padding: "20px", marginBottom: 24,
          }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.12em", marginBottom: 16, textTransform: "uppercase", fontWeight: "bold" }}>
              Alternative Hospitals
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {result.alternatives.map((alt, i) => (
                <AlternativeRow
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
            background: "#1e293b", border: "1px solid #334155",
            borderRadius: 12, padding: "14px 18px", marginBottom: 20,
            display: "flex", gap: 24, flexWrap: "wrap",
          }}>
            <div style={{ fontSize: 10, color: "#64748b", letterSpacing: "0.1em", textTransform: "uppercase", alignSelf: "center", fontWeight: "bold" }}>
              Filtered out:
            </div>
            {result.rejected_hospitals.missing_equipment > 0 && (
              <span style={{ fontSize: 12, color: "#cbd5e1" }}>
                <span style={{ color: "#ef4444", fontWeight: 700, fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>{result.rejected_hospitals.missing_equipment}</span> missing equipment
              </span>
            )}
            {result.rejected_hospitals.insufficient_beds > 0 && (
              <span style={{ fontSize: 12, color: "#cbd5e1" }}>
                <span style={{ color: "#ef4444", fontWeight: 700, fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>{result.rejected_hospitals.insufficient_beds}</span> insufficient beds
              </span>
            )}
            {result.rejected_hospitals.too_far > 0 && (
              <span style={{ fontSize: 12, color: "#cbd5e1" }}>
                <span style={{ color: "#ef4444", fontWeight: 700, fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>{result.rejected_hospitals.too_far}</span> too far
              </span>
            )}
            <span style={{ fontSize: 12, color: "#64748b", marginLeft: "auto", fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>
              {result.rejected_hospitals.total_evaluated} evaluated
            </span>
          </div>
        )}

        {/* ── CASE TIMELINE (fully integrated dark theme) ── */}
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
          marginTop: 24, padding: "12px 0",
          borderTop: "1px solid #334155",
          display: "flex", justifyContent: "space-between",
          fontSize: 10, color: "#64748b",
        }}>
          <span>DATA SOURCE: {sh?.data_source?.toUpperCase() || "LIVE"}</span>
          <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>LAST UPDATED: {sh?.last_updated ? new Date(sh.last_updated).toLocaleTimeString() : "—"}</span>
        </div>
      </div>
    </div>
  );
}
