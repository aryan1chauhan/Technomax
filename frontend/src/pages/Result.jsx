/**
 * Result.jsx — Redesigned emergency medical dispatch UI.
 *
 * Fully conforms to the premium light theme specifications:
 *   - Background: #F7F7FC
 *   - Cards: white / glass-card (.glass-card)
 *   - Borders: #E2E6F0
 *   - Monospace font for data values, clean sans-serif (Inter) for labels and names.
 *   - Overall layout: single-column centered with max-width 960px.
 */

import { useLocation, useNavigate } from "react-router-dom";
import { useState, useEffect, lazy, Suspense } from "react";
import CaseTimeline from "../components/CaseTimeline";
import api from "../api/axios";
import useCaseSocket from "../hooks/useCaseSocket";

const CaseChat = lazy(() => import("../components/CaseChat"));
const CallPanel = lazy(() => import("../components/CallPanel"));

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
  if (pct >= 80) return "#17B86B"; // Green (80-100)
  if (pct >= 40) return "#FFB21A"; // Amber (40-79)
  return "#EE3B3B";                // Red (0-39)
}

// ── Custom Circular Score Ring Gauge ────────────────────────────────────────
function ScoreRing({ value, size = 80, label, isLarge = false }) {
  const r = (size - 10) / 2;
  const circ = 2 * Math.PI * r;
  const filled = circ * value;
  const color = scoreColor(value);
  const pct = Math.round(value * 100);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="transform -rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#E2E6F0" strokeWidth={isLarge ? 8 : 6} />
          <circle
            cx={size / 2} cy={size / 2} r={r}
            fill="none"
            stroke={color}
            strokeWidth={isLarge ? 8 : 6}
            strokeDasharray={`${filled} ${circ - filled}`}
            strokeLinecap="round"
            className="transition-all duration-500 ease-out"
          />
        </svg>
        <div 
          className="absolute inset-0 flex items-center justify-center font-mono font-bold"
          style={{
            fontSize: isLarge ? `${size * 0.26}px` : `${size * 0.24}px`,
            color: color,
          }}
        >
          {pct}
        </div>
      </div>
      <span className="text-[10px] text-[#737A8F] uppercase tracking-wider font-semibold text-center">
        {label}
      </span>
    </div>
  );
}

// ── Chip ─────────────────────────────────────────────────────────────────────
function Chip({ text, positive }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-semibold border ${
        positive
          ? "bg-[#E8FDF4] border-[#B3F5D9] text-[#148A52]"
          : "bg-[#FFF0F0] border-[#FFCDD2] text-[#EE3B3B]"
      }`}
    >
      <span className="text-[8px]">{positive ? "▲" : "▼"}</span>
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
      className={`border border-[#E2E6F0] rounded-xl p-4 flex flex-col gap-3 transition-all duration-200 ${
        hovered ? "bg-[#F8FAFC] shadow-sm translate-y-[-1px]" : "bg-white"
      }`}
    >
      <div className="flex justify-between items-center flex-wrap gap-2">
        {/* Left side: Rank badge + Hospital Name */}
        <div className="flex items-center gap-2.5">
          <span className="text-[10px] font-mono font-bold text-[#737A8F] bg-[#F1F3F9] border border-[#D0D5E8] px-2 py-0.5 rounded uppercase">
            ALT {index + 1}
          </span>
          <span className="font-bold text-[#1A1E2E] text-[15px]">
            {hospital.name}
          </span>
        </div>

        {/* Right side: Score badge + Override button */}
        <div className="flex items-center gap-3">
          <div
            className="font-mono font-bold text-[13px] px-2.5 py-1 rounded-lg border"
            style={{
              color: badgeColor,
              backgroundColor: `${badgeColor}15`,
              borderColor: `${badgeColor}30`,
            }}
          >
            {scorePercent}%
          </div>
          <button
            onClick={() => onOverride(hospital)}
            className={`px-3.5 py-1.5 rounded-lg text-[11px] font-bold border transition-all duration-200 cursor-pointer ${
              hovered
                ? "bg-[#FFB21A] border-[#FFB21A] text-white"
                : "bg-white border-[#FFE8B3] text-[#FFB21A] hover:bg-[#FFE8B3]"
            }`}
          >
            OVERRIDE
          </button>
        </div>
      </div>

      {/* Row Data pills */}
      <div className="flex gap-2 flex-wrap">
        {/* Distance pill */}
        <div className="flex items-center gap-1.5 bg-[#F8FAFC] border border-[#E2E6F0] px-2.5 py-1 rounded-full text-[12px] text-[#4A5068]">
          <span>📍</span>
          <span className="font-mono font-semibold">
            {hospital.distance_km} km
          </span>
        </div>

        {/* Bed pill */}
        <div className="flex items-center gap-1.5 bg-[#F8FAFC] border border-[#E2E6F0] px-2.5 py-1 rounded-full text-[12px] text-[#4A5068]">
          <span>🛏</span>
          <span className="font-mono font-semibold">
            {hospital.available_beds} beds
          </span>
        </div>

        {/* ETA pill */}
        <div className="flex items-center gap-1.5 bg-[#F8FAFC] border border-[#E2E6F0] px-2.5 py-1 rounded-full text-[12px] text-[#4A5068]">
          <span>⏱</span>
          <span className="font-mono font-semibold">
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
    <div className="max-w-[960px] mx-auto px-8 py-8 font-sans text-[#4A5068]">
      <div className="glass-card rounded-2xl border border-[#E2E6F0] p-8 text-center mb-6 bg-white shadow-sm">
        <div className="text-5xl mb-4">{isConstraintFailure ? "🚫" : "⚠️"}</div>
        <div className="text-[#EE3B3B] text-xl font-extrabold mb-3">
          No Eligible Hospital Found
        </div>
        <div className="text-[#737A8F] text-[14px] leading-relaxed mb-4">
          {humanReason}
        </div>
        {isConstraintFailure && (
          <div className="inline-block px-3 py-1 rounded-full text-[11px] font-mono bg-[#FFF0F0] border border-[#FFCDD2] text-[#EE3B3B]">
            {rawReason}
          </div>
        )}
      </div>

      {rh ? (
        <div className="glass-card rounded-2xl border border-[#E2E6F0] p-6 mb-6 bg-white shadow-sm">
          <div className="text-[#737A8F] text-[11px] font-bold uppercase tracking-wider mb-4">
            Rejection Breakdown
          </div>
          <div className="flex flex-col gap-3">
            {[
              ["Missing equipment", rh.missing_equipment],
              ["Insufficient beds", rh.insufficient_beds],
              ["Too far",           rh.too_far],
            ].map(([label, count]) => (count ?? 0) > 0 && (
              <div key={label} className="flex justify-between py-2 border-b border-[#E2E6F0] text-[14px] text-[#4A5068]">
                <span>{label}</span>
                <span className="text-[#EE3B3B] font-mono font-bold">{count}</span>
              </div>
            ))}
          </div>
          {(rh.total_evaluated ?? 0) > 0 && (
            <div className="text-[11px] text-[#9EA6BC] mt-3 text-right font-mono">
              {rh.total_evaluated} hospitals evaluated
            </div>
          )}
        </div>
      ) : isConstraintFailure && (
        <div className="glass-card rounded-2xl border border-[#E2E6F0] p-4 mb-6 text-[13px] text-[#737A8F] leading-relaxed bg-white">
          All hospitals in range were evaluated and excluded by capability constraints.
          No trauma-capable facility was available at the time of dispatch.
        </div>
      )}

      {result.fallback_options?.length > 0 && (
        <div className="glass-card rounded-2xl border border-[#E2E6F0] p-6 mb-6 bg-white shadow-sm">
          <div className="text-[#737A8F] text-[11px] font-bold uppercase tracking-wider mb-4">
            Nearest Hospitals (Equipment Not Guaranteed)
          </div>
          {result.fallback_options.map((opt, i) => (
            <div key={i} className="text-[#4A5068] text-[14px] py-2 border-b border-[#E2E6F0] last:border-0">
              {opt}
            </div>
          ))}
        </div>
      )}

      <button
        onClick={onNewDispatch}
        className="w-full py-3.5 rounded-xl font-bold text-[14px] bg-[#FFF0F0] hover:bg-[#FFCDD2] border border-[#FFCDD2] text-[#EE3B3B] transition-all duration-200 cursor-pointer"
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
  const [panelMode, setPanelMode] = useState(null);

  const {
    socketStatus,
    lastEvent,
    socket,
  } = useCaseSocket(result?.case_id, Boolean(result?.case_id && panelMode));

  useEffect(() => { setTimeout(() => setMounted(true), 50); }, []);

  if (!result) {
    return (
      <div className="min-h-screen bg-[#F7F7FC] flex flex-col items-center justify-center text-[#737A8F] font-sans">
        <div className="text-4xl mb-4">🚑</div>
        <div className="text-[15px] font-medium mb-3">No dispatch result found.</div>
        <button
          onClick={() => navigate("/dispatch")}
          className="px-4 py-2 rounded-xl bg-[#1A78F2] text-white text-[13px] font-semibold transition-all hover:bg-[#1565C0] cursor-pointer"
        >
          Return to Dispatch
        </button>
      </div>
    );
  }

  if (result.no_match) {
    return (
      <div className="min-h-screen bg-[#F7F7FC] pb-10">
        <nav className="glass-panel sticky top-0 z-50 h-16 flex items-center px-8 mb-4">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative w-9 h-9 bg-[#EE3B3B] rounded-lg flex items-center justify-center">
              <div className="absolute w-4 h-1.5 bg-white rounded-sm" />
              <div className="absolute w-1.5 h-4 bg-white rounded-sm" />
            </div>
            <div>
              <p className="text-[16px] font-bold premium-gradient-text leading-none">MediRoute</p>
              <p className="text-[11px] text-[#737A8F]">Premium Dispatch</p>
            </div>
          </div>
        </nav>
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
      <div className="min-h-screen bg-[#F7F7FC] pb-10">
        <nav className="glass-panel sticky top-0 z-50 h-16 flex items-center px-8 mb-4">
          <div className="flex items-center gap-3 flex-1">
            <div className="relative w-9 h-9 bg-[#EE3B3B] rounded-lg flex items-center justify-center">
              <div className="absolute w-4 h-1.5 bg-white rounded-sm" />
              <div className="absolute w-1.5 h-4 bg-white rounded-sm" />
            </div>
            <div>
              <p className="text-[16px] font-bold premium-gradient-text leading-none">MediRoute</p>
              <p className="text-[11px] text-[#737A8F]">Premium Dispatch</p>
            </div>
          </div>
        </nav>
        <NoMatchView result={syntheticResult} onNewDispatch={() => navigate("/dispatch")} />
      </div>
    );
  }

  const triage = result.triage || {};
  const severity = (triage.severity || "moderate").toLowerCase();

  // Mapped left border and badge colors to match light theme Dispatch.jsx
  const severityColor =
    severity === "critical" ? "#EE3B3B" :
    severity === "moderate" ? "#FFB21A" : "#17B86B";

  const severityBg =
    severity === "critical" ? "#FFF0F0" :
    severity === "moderate" ? "#FFF8E8" : "#E8FDF4";
  const severityText =
    severity === "critical" ? "#EE3B3B" :
    severity === "moderate" ? "#FFB21A" : "#17B86B";
  const severityBorder =
    severity === "critical" ? "#FFCDD2" :
    severity === "moderate" ? "#FFE8B3" : "#B3F5D9";

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

  const handleOverride = async (altHospital) => {
    try {
      if (result.case_id) {
        await api.put(`/api/cases/${result.case_id}/override-hospital`, {
          new_hospital_id: altHospital.hospital_id,
          distance_km: altHospital.distance_km,
          eta_minutes: altHospital.eta_minutes,
          final_score: altHospital.score,
        });
      }
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
    } catch (err) {
      console.error("Failed to override hospital routing:", err);
      alert(err.response?.data?.detail || "Failed to override hospital routing. Please try again.");
    }
  };

  return (
    <div className="min-h-screen bg-[#F7F7FC] font-sans pb-10 text-[#4A5068]">
      {/* ── Sticky Header bar ── */}
      <nav className="glass-panel sticky top-0 z-50 h-16 flex items-center px-8 mb-4">
        <div className="flex items-center gap-3 flex-1">
          <div className="relative w-9 h-9 bg-[#EE3B3B] rounded-lg flex items-center justify-center">
            <div className="absolute w-4 h-1.5 bg-white rounded-sm" />
            <div className="absolute w-1.5 h-4 bg-white rounded-sm" />
          </div>
          <div>
            <p className="text-[16px] font-bold premium-gradient-text leading-none">MediRoute</p>
            <p className="text-[11px] text-[#737A8F]">Premium Dispatch Result</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate("/map", { state })}
            className="px-4 py-2 rounded-xl text-[13px] font-semibold text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] transition-all duration-200 hover:bg-[#1A78F2] hover:text-white cursor-pointer"
          >
            VIEW MAP →
          </button>
          <button
            onClick={() => navigate("/dispatch")}
            className="px-4 py-2 rounded-xl border border-[#D0D5E8] text-[13px] font-semibold text-[#1A1E2E] bg-white transition-all duration-200 hover:bg-[#F7F7FC] cursor-pointer"
          >
            NEW DISPATCH
          </button>
        </div>
      </nav>

      {/* Main Single Column Wrapper */}
      <div className="max-w-[960px] mx-auto px-8 py-4">

        {/* ── TOP CARD: Primary Dispatch Result ── */}
        <div
          className="bg-white border-y border-r border-[#E2E6F0] rounded-2xl p-6 mb-6 shadow-sm transition-all duration-500"
          style={{
            borderLeft: `6px solid ${severityColor}`,
            opacity: mounted ? 1 : 0,
            transform: mounted ? "translateY(0)" : "translateY(12px)",
          }}
        >
          <div className="flex flex-col gap-3">
            {/* Severity Badge + Plain Text Condition */}
            <div className="flex items-center gap-3">
              <span 
                className="px-3 py-1 rounded-full text-[11px] font-extrabold tracking-wider border uppercase"
                style={{
                  backgroundColor: severityBg,
                  color: severityText,
                  borderColor: severityBorder,
                }}
              >
                {severity}
              </span>
              <span className="text-[#737A8F] text-[14px] font-medium capitalize">
                {triage.condition?.replace(/_/g, " ")}
              </span>
            </div>

            {/* Hospital Name (large & prominent) */}
            <h2 className="text-2xl font-extrabold text-[#1A1E2E] tracking-tight">
              {sh?.name}
            </h2>

            {/* Address */}
            <p className="text-[13px] text-[#737A8F] flex items-center gap-1.5">
              <span>📍</span> {sh?.address || "Address not available"}
            </p>

            {/* Stat Pills in a Row */}
            <div className="flex gap-3 flex-wrap mt-1">
              {/* Distance Pill */}
              <div className="flex items-center gap-2 bg-[#EBF3FF] border border-[#BDD6FF] px-3.5 py-1.5 rounded-full text-[13px] text-[#1A78F2] font-semibold">
                <span>📍</span>
                <span className="font-mono">
                  {sh?.distance_km} km
                </span>
              </div>

              {/* ETA Pill */}
              <div className="flex items-center gap-2 bg-[#E8FDF4] border border-[#B3F5D9] px-3.5 py-1.5 rounded-full text-[13px] text-[#17B86B] font-semibold">
                <span>⏱</span>
                <span className="font-mono">
                  {sh?.eta_minutes} min
                </span>
              </div>

              {/* Beds Pill */}
              <div className="flex items-center gap-2 bg-[#F3EBF9] border border-[#E1C6F4] px-3.5 py-1.5 rounded-full text-[13px] text-[#8E44AD] font-semibold">
                <span>🛏</span>
                <span className="font-mono">
                  {sh?.available_beds} beds
                </span>
              </div>
            </div>

            {result.case_id && (
              <div className="flex gap-3 mt-4 pt-4 border-t border-[#F0F2F7]">
                <button
                  onClick={() => setPanelMode(panelMode === "chat" ? null : "chat")}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-[13px] font-bold border transition cursor-pointer ${
                    panelMode === "chat"
                      ? "bg-[#1A78F2] border-[#1A78F2] text-white shadow-sm"
                      : "bg-white border-[#BDD6FF] text-[#1A78F2] hover:bg-[#F0F6FF]"
                  }`}
                >
                  💬 Chat
                </button>
                <button
                  onClick={() => setPanelMode(panelMode === "call" ? null : "call")}
                  className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-[13px] font-bold border transition cursor-pointer ${
                    panelMode === "call"
                      ? "bg-[#1A78F2] border-[#1A78F2] text-white shadow-sm"
                      : "bg-white border-[#BDD6FF] text-[#1A78F2] hover:bg-[#F0F6FF]"
                  }`}
                >
                  📞 Video Call
                </button>
              </div>
            )}
          </div>
        </div>

        {/* ── CASE COMMUNICATIONS PANEL ── */}
        {result.case_id && panelMode && (
          <div 
            className="bg-white rounded-2xl border border-[#E2E6F0] shadow-sm p-5 mb-6 transition-all duration-500"
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(12px)",
            }}
          >
            <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
              <div>
                <p className="text-[15px] font-bold text-[#1A1E2E]">Case Communications</p>
                <p className="text-[12px] text-[#737A8F]">
                  Ambulance dispatcher secure channel · Case #{result.case_id}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] uppercase tracking-wide text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-3 py-1">
                  Socket {socketStatus}
                </span>
                <button
                  onClick={() => setPanelMode(null)}
                  className="rounded-xl border border-[#D0D5E8] px-3.5 py-1.5 text-[12px] font-semibold text-[#4A5068] hover:bg-gray-50 transition cursor-pointer"
                >
                  Close
                </button>
              </div>
            </div>

            {panelMode === "chat" && (
              <Suspense fallback={<div className="text-center py-4 text-[#737A8F] text-[13px]">Loading case chat...</div>}>
                <CaseChat
                  caseId={result.case_id}
                  caseLabel={`${triage.condition?.replace(/_/g, " ") || "Case"} · Case #${result.case_id}`}
                  socketEvent={lastEvent}
                />
              </Suspense>
            )}

            {panelMode === "call" && (
              <Suspense fallback={<div className="text-center py-4 text-[#737A8F] text-[13px]">Loading call controls...</div>}>
                <CallPanel
                  socket={socket}
                  caseId={result.case_id}
                  role="paramedic"
                  remoteLabel={`${sh?.name || "Hospital Staff"}`}
                  onClose={() => setPanelMode(null)}
                />
              </Suspense>
            )}
          </div>
        )}

        {/* ── Two-hop route (stabilize first only) ── */}
        {isStabilizeFirst && (
          <div 
            className="glass-card rounded-2xl border border-[#E2E6F0] p-5 mb-6 transition-all duration-500 bg-white"
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(12px)",
            }}
          >
            <div className="text-[11px] font-bold text-[#737A8F] uppercase tracking-wider mb-3">
              Two-Step Route
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
              <div className="bg-[#F8FAFC] border border-[#E2E6F0] rounded-xl p-3">
                <div className="text-[11px] font-bold text-[#FFB21A] mb-1.5 tracking-wider uppercase">
                  STEP 1: STABILIZATION HOSPITAL
                </div>
                <div className="text-[#1A1E2E] font-bold text-[14px] mb-1">
                  {destinationName(routePrimary)}
                </div>
                <div className="text-[12px] text-[#737A8F] font-mono">
                  ETA: {destinationEta(routePrimary)} min
                </div>
                <div className="text-[12px] text-[#737A8F] font-mono">
                  Distance: {destinationDistance(routePrimary)} km
                </div>
              </div>
              <div className="bg-[#F8FAFC] border border-[#E2E6F0] rounded-xl p-3">
                <div className="text-[11px] font-bold text-[#1A78F2] mb-1.5 tracking-wider uppercase">
                  STEP 2: FINAL HOSPITAL
                </div>
                <div className="text-[#1A1E2E] font-bold text-[14px] mb-1">
                  {destinationName(routeSecondary)}
                </div>
                <div className="text-[12px] text-[#737A8F] font-mono">
                  ETA: {routeSecondary ? destinationEta(routeSecondary) : "-"} min
                </div>
                <div className="text-[12px] text-[#737A8F] font-mono">
                  Distance: {routeSecondary ? destinationDistance(routeSecondary) : "-"} km
                </div>
              </div>
            </div>
            <div className="flex gap-4 flex-wrap text-[12px] items-center">
              <span className="text-[#4A5068]">
                Stability Score:{" "}
                <strong className="font-mono" style={{ color: scoreColor(stabilityScore) }}>
                  {Math.round(stabilityScore * 100)}%
                </strong>
              </span>
              <span className="text-[#EE3B3B] bg-[#FFF0F0] border border-[#FFCDD2] px-2 py-0.5 rounded">
                Reason for diversion: {diversionText}
              </span>
            </div>
          </div>
        )}

        {/* ── SCORE BREAKDOWN RINGS ── */}
        <div 
          className="glass-card rounded-2xl border border-[#E2E6F0] p-6 mb-6 bg-white transition-all duration-500"
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? "translateY(0)" : "translateY(12px)",
          }}
        >
          <div className="text-[11px] font-bold text-[#737A8F] uppercase tracking-wider mb-5">
            Score Breakdown
          </div>
          
          {/* Top Row: 4 sub-gauges identical in size and style */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 justify-items-center w-full mb-6">
            <ScoreRing value={breakdown.distance  ?? 0} label="Distance" size={80} />
            <ScoreRing value={breakdown.beds       ?? 0} label="Capacity" size={80} />
            <ScoreRing value={breakdown.specialist ?? 0} label="Specialist" size={80} />
            <ScoreRing value={breakdown.equipment  ?? 1} label="Equipment" size={80} />
          </div>

          {/* Bottom Row: Largest centered Overall match gauge */}
          <div className="flex flex-col items-center w-full">
            <ScoreRing value={sh?.score ?? 0} label="Overall Match" size={110} isLarge />
            {(breakdown.ml_confidence ?? 0) > 0 && (
              <div className="flex items-center gap-1.5 mt-3.5 px-3.5 py-1.5 rounded-full bg-[#F7F7FC] border border-[#E2E6F0]">
                <span className="text-[10px] text-[#737A8F] font-bold tracking-wider uppercase">
                  ML Confidence
                </span>
                <span 
                  className="font-mono font-bold text-[12px]"
                  style={{ color: scoreColor(breakdown.ml_confidence) }}
                >
                  {Math.round(breakdown.ml_confidence * 100)}%
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ── Explanation + pros/cons ── */}
        <div 
          className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6 transition-all duration-500"
          style={{
            opacity: mounted ? 1 : 0,
            transform: mounted ? "translateY(0)" : "translateY(12px)",
          }}
        >
          {/* Explanation */}
          <div className="glass-card rounded-2xl border border-[#E2E6F0] p-5 bg-white">
            <div className="text-[11px] font-bold text-[#737A8F] uppercase tracking-wider mb-3">
              Reasoning
            </div>
            {(sh?.explanation || []).map((line, i) => (
              <div 
                key={i} 
                className="text-[13px] text-[#4A5068] leading-relaxed pb-2 border-b border-[#E2E6F0] last:border-0 last:pb-0 mb-2 last:mb-0"
              >
                {line}
              </div>
            ))}
          </div>

          {/* Pros / Cons */}
          <div className="glass-card rounded-2xl border border-[#E2E6F0] p-5 bg-white">
            <div className="text-[11px] font-bold text-[#737A8F] uppercase tracking-wider mb-3">
              Pros / Cons
            </div>
            <div className="flex flex-wrap gap-2">
              {(sh?.pros || []).map((p, i) => <Chip key={`p-${i}`} text={p} positive />)}
              {(sh?.cons || []).map((c, i) => <Chip key={`c-${i}`} text={c} positive={false} />)}
            </div>
          </div>
        </div>

        {/* ── ALTERNATIVE HOSPITALS ── */}
        {result.alternatives?.length > 0 && (
          <div 
            className="glass-card rounded-2xl border border-[#E2E6F0] p-6 mb-6 bg-white transition-all duration-500"
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(12px)",
            }}
          >
            <div className="text-[11px] font-bold text-[#737A8F] uppercase tracking-wider mb-4">
              Alternative Hospitals
            </div>
            <div className="flex flex-col gap-3">
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
          <div 
            className="glass-card rounded-2xl border border-[#E2E6F0] p-4 mb-6 flex gap-6 flex-wrap items-center bg-white transition-all duration-500"
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(12px)",
            }}
          >
            <div className="text-[10px] font-bold text-[#737A8F] uppercase tracking-wider">
              Filtered out:
            </div>
            {result.rejected_hospitals.missing_equipment > 0 && (
              <span className="text-[12px] text-[#4A5068]">
                <span className="text-[#EE3B3B] font-mono font-bold">{result.rejected_hospitals.missing_equipment}</span> missing equipment
              </span>
            )}
            {result.rejected_hospitals.insufficient_beds > 0 && (
              <span className="text-[12px] text-[#4A5068]">
                <span className="text-[#EE3B3B] font-mono font-bold">{result.rejected_hospitals.insufficient_beds}</span> insufficient beds
              </span>
            )}
            {result.rejected_hospitals.too_far > 0 && (
              <span className="text-[12px] text-[#4A5068]">
                <span className="text-[#EE3B3B] font-mono font-bold">{result.rejected_hospitals.too_far}</span> too far
              </span>
            )}
            <span className="text-[12px] text-[#737A8F] font-mono ml-auto">
              {result.rejected_hospitals.total_evaluated} evaluated
            </span>
          </div>
        )}

        {/* ── CASE TIMELINE (fully integrated light theme) ── */}
        {result.case_id && (
          <div 
            className="transition-all duration-500"
            style={{
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(12px)",
            }}
          >
            <CaseTimeline caseId={result.case_id} theme="light" />
          </div>
        )}

        {/* ── Data source footer ── */}
        <div className="mt-6 pt-4 border-t border-[#E2E6F0] flex justify-between text-[10px] text-[#737A8F] font-semibold tracking-wider">
          <span>DATA SOURCE: {sh?.data_source?.toUpperCase() || "LIVE"}</span>
          <span className="font-mono">LAST UPDATED: {sh?.last_updated ? new Date(sh.last_updated).toLocaleTimeString() : "—"}</span>
        </div>
      </div>
    </div>
  );
}
