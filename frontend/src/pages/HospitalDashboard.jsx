import { lazy, Suspense, useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import api from "../api/axios";
import RouteFallback from "../components/RouteFallback";
import useCaseSocket from "../hooks/useCaseSocket";
import useFCM from "../hooks/useFCM";

const CaseChat = lazy(() => import("../components/CaseChat"));
const CallPanel = lazy(() => import("../components/CallPanel"));

export default function HospitalDashboard() {
  const navigate  = useNavigate();
  const [cases,   setCases]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [hospitalInfo, setHospitalInfo] = useState({ name: "Hospital", id: "", beds: "—" });
  const [declineReasons, setDeclineReasons] = useState({});
  const [actionLoading, setActionLoading] = useState({});
  const [actionError, setActionError] = useState("");
  const [selectedCase, setSelectedCase] = useState(null);
  const [panelMode, setPanelMode] = useState(null);
  const [pushBanner, setPushBanner] = useState(null);

  // ── FCM Push Notifications ──
  // Registers the browser for push on mount; foreground pushes arrive via lastPush
  const { lastPush, fcmStatus } = useFCM();
  const lastPushIdRef = useRef(null);

  // Auto-refresh case list when a foreground push notification arrives
  // NOTE: This effect must be placed AFTER fetchCases is defined via useCallback
  // to avoid referencing an undefined function during the initial render.

  const fetchCases = useCallback(async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) { navigate("/login"); return; }
      const res = await api.get("/api/cases/hospital");
      const data = Array.isArray(res.data) ? res.data : (res.data.items || []);
      setCases(data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));
    } catch (err) {
      if (err?.response?.status === 401) {
        localStorage.clear();
        navigate("/login");
      } else {
        console.error("Failed to fetch hospital cases", err);
      }
    } finally { setLoading(false); }
  }, [navigate]);

  useEffect(() => {
    if (!lastPush || lastPush.receivedAt === lastPushIdRef.current) return;
    lastPushIdRef.current = lastPush.receivedAt;

    // Show a brief banner
    setPushBanner(lastPush);
    const timer = setTimeout(() => setPushBanner(null), 6000);

    // Immediately refresh case list so the new case appears
    fetchCases();

    return () => clearTimeout(timer);
  }, [lastPush, fetchCases]);

  useEffect(() => {
    fetchCases();
    // Decode JWT to get hospital_id, then fetch hospital name + beds
    try {
      const token = localStorage.getItem("token");
      if (token) {
        const decoded = jwtDecode(token);
        const hid = decoded.hospital_id;
        if (hid) {
          api.get("/api/hospitals/").then(res => {
            const h = res.data.find(h => h.id === hid);
            if (h) setHospitalInfo({
              name: h.name,
              id: hid,
              beds: h.availability?.beds ?? "—",
            });
          }).catch((err) => {
            console.error("Failed to fetch hospital info", err);
          });
        }
      }
    } catch (err) {
      console.error("Failed to decode hospital token", err);
    }
    const t = setInterval(fetchCases, 10000);
    return () => clearInterval(t);
  }, [fetchCases]);

  useEffect(() => {
    if (!selectedCase) return;
    const freshCase = cases.find((item) => item.id === selectedCase.id);
    if (freshCase) {
      setSelectedCase(freshCase);
    }
  }, [cases, selectedCase]);

  const {
    socketStatus: selectedCaseSocketStatus,
    lastEvent: selectedCaseSocketEvent,
    sendEvent: sendSelectedCaseEvent,
    socket: selectedCaseSocket,
  } = useCaseSocket(selectedCase?.id, Boolean(selectedCase && panelMode));

  const todayCount  = cases.filter(c => {
    const d = new Date(c.created_at), now = new Date();
    return d.getDate()===now.getDate() && d.getMonth()===now.getMonth() && d.getFullYear()===now.getFullYear();
  }).length;
  const incomingCases = cases.filter(c => c.status === "dispatched");
  const activeStatuses = new Set(["accepted", "en_route", "on_scene", "transporting", "arrived", "stabilized", "en_route_secondary"]);
  const activeCases = cases.filter(c => activeStatuses.has(c.status));
  const avgScore    = cases.length ? Math.round(cases.reduce((a, c) => a + (c.final_score||0), 0) / cases.length * 100) : 0;
  const timeAgo     = ds => { const m = Math.round((new Date()-new Date(ds))/60000); return m===0?"Just now":`${m}m ago`; };
  const scoreColor  = s => s > 70 ? "#17B86B" : s > 50 ? "#FFB21A" : "#EE3B3B";
  const scoreBg     = s => s > 70 ? "#E8FDF2" : s > 50 ? "#FFF8E0" : "#FFEDED";
  const fmtStatus   = s => (s || "dispatched").replace(/_/g, " ").toUpperCase();

  const acceptCase = async (caseId) => {
    setActionError("");
    setActionLoading(prev => ({ ...prev, [caseId]: "accept" }));
    try {
      await api.post(`/api/cases/${caseId}/accept`);
      await fetchCases();
    } catch (err) {
      setActionError(err?.response?.data?.detail || "Could not accept case.");
    } finally {
      setActionLoading(prev => ({ ...prev, [caseId]: null }));
    }
  };

  const declineCase = async (caseId) => {
    const reason = (declineReasons[caseId] || "").trim();
    if (!reason) {
      setActionError("Decline reason is required.");
      return;
    }
    setActionError("");
    setActionLoading(prev => ({ ...prev, [caseId]: "decline" }));
    try {
      await api.post(`/api/cases/${caseId}/decline`, { reason });
      setDeclineReasons(prev => ({ ...prev, [caseId]: "" }));
      await fetchCases();
    } catch (err) {
      setActionError(err?.response?.data?.detail || "Could not decline case.");
    } finally {
      setActionLoading(prev => ({ ...prev, [caseId]: null }));
    }
  };

  const openPanel = (caseRecord, mode) => {
    setSelectedCase(caseRecord);
    setPanelMode((prev) => (prev === mode && selectedCase?.id === caseRecord.id ? null : mode));
  };

  const navItems = ["🏥  Dashboard", "🚑  Active Cases", "📊  Analytics", "⚙️  Settings"];

  return (
    <div className="flex h-screen bg-[#F7F7FC] font-['Inter',sans-serif] overflow-hidden">

      {/* ── Sidebar ── */}
      <aside className="w-[240px] bg-[#0D1830] flex-shrink-0 flex flex-col relative">
        <div className="absolute left-0 top-0 w-[3px] h-full bg-[#EE3B3B]" />
        <div className="px-7 pt-7 pb-5">
          <p className="text-[18px] font-bold text-white">MediRoute</p>
          <p className="text-[12px] text-[#737A8F]">Hospital Portal</p>
        </div>
        <nav className="flex flex-col gap-1 px-3">
          {navItems.map((item, i) => (
            <div
              key={i}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl text-[14px] cursor-pointer transition
                ${i === 0 ? "bg-[#172954] text-white font-semibold border-l-[3px] border-[#1A78F2]" : "text-[#737A8F] hover:text-white"}`}
            >
              {item}
            </div>
          ))}
        </nav>
        <div className="mt-auto px-7 pb-6 border-t border-[#172954] pt-5">
          <p className="text-[13px] font-semibold text-white">{localStorage.getItem("email") || "Bhagwati Hospital"}</p>
          <p className="text-[12px] text-[#737A8F]">{hospitalInfo.name} · ID #{hospitalInfo.id}</p>
          <div className="flex items-center gap-2 mt-2">
            <div className="w-2 h-2 rounded-full bg-[#17B86B]" />
            <p className="text-[12px] text-[#17B86B]">Accepting cases</p>
          </div>
          <button
            onClick={() => { localStorage.clear(); navigate("/login"); }}
            className="mt-3 text-[12px] text-[#737A8F] hover:text-white transition"
          >
            Sign out →
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <div className="bg-white border-b border-[#F0F2F7] h-16 flex items-center justify-between px-8">
          <h1 className="text-[22px] font-bold text-[#1A1E2E]">Incoming Emergency Cases</h1>
          <div className="flex items-center gap-3">
            {cases.length > 0 && (
              <span className="flex items-center gap-2 bg-[#FFEDED] text-[#EE3B3B] text-[11px] font-bold px-3 py-1.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-[#EE3B3B] animate-pulse" />
                {incomingCases.length} INCOMING
              </span>
            )}
            <span className="text-[11px] text-[#737A8F] bg-[#F0F2F7] px-3 py-1.5 rounded-full">↻ Live · 10s</span>
            {fcmStatus === "ready" && (
              <span className="text-[11px] text-[#17B86B] bg-[#E8FDF2] px-3 py-1.5 rounded-full">🔔 Push ON</span>
            )}
            {fcmStatus === "denied" && (
              <span className="text-[11px] text-[#FFB21A] bg-[#FFF8E0] px-3 py-1.5 rounded-full">🔕 Push Blocked</span>
            )}
          </div>
        </div>

        {/* ── Push notification toast banner ── */}
        {pushBanner && (
          <div className="mx-8 mt-3 flex items-center gap-3 bg-gradient-to-r from-[#1A78F2] to-[#6C4BEF] text-white rounded-xl px-5 py-3 shadow-lg animate-pulse">
            <span className="text-[20px]">🚨</span>
            <div className="flex-1">
              <p className="text-[13px] font-bold">{pushBanner.title}</p>
              <p className="text-[12px] opacity-90">{pushBanner.body}</p>
            </div>
            <button
              onClick={() => setPushBanner(null)}
              className="text-white/70 hover:text-white text-[18px] font-bold"
            >
              ✕
            </button>
          </div>
        )}

        <div className="p-8">
          {/* Stats row */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            {[
              { val: todayCount,    label: "Cases Today",    accent: "#EE3B3B" },
              { val: activeCases.length,  label: "Active Cases",   accent: "#1A78F2" },
              { val: `${avgScore}%`,label: "Avg ML Score",   accent: "#17B86B" },
              { val: hospitalInfo.beds, label: "Beds Available", accent: "#FFB21A" },
            ].map(({ val, label, accent }) => (
              <div key={label} className="bg-white rounded-xl border border-[#F0F2F7] overflow-hidden">
                <div className="h-1" style={{ backgroundColor: accent }} />
                <div className="p-5">
                  <p className="text-[32px] font-extrabold text-[#1A1E2E]">{val}</p>
                  <p className="text-[12px] text-[#737A8F] mt-1">{label}</p>
                </div>
              </div>
            ))}
          </div>

          {selectedCase && panelMode && (
            <div className="mb-8">
              <div className="bg-white rounded-2xl border border-[#E2E6F0] shadow-sm p-5">
                <div className="flex items-center justify-between flex-wrap gap-3 mb-4">
                  <div>
                    <p className="text-[15px] font-bold text-[#1A1E2E]">Case Communications</p>
                    <p className="text-[12px] text-[#737A8F]">
                      {(selectedCase.custom_condition || selectedCase.condition || "case").replace(/_/g, " ")} · Case #{selectedCase.id}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[11px] uppercase tracking-wide text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-3 py-1">
                      Socket {selectedCaseSocketStatus}
                    </span>
                    <button
                      onClick={() => openPanel(selectedCase, "chat")}
                      className="rounded-xl border border-[#D0D5E8] px-4 py-2 text-[13px] font-semibold text-[#1A1E2E]"
                    >
                      Chat
                    </button>
                    <button
                      onClick={() => openPanel(selectedCase, "call")}
                      className="rounded-xl bg-[#1A78F2] px-4 py-2 text-[13px] font-semibold text-white"
                    >
                      Call
                    </button>
                  </div>
                </div>

                {panelMode === "chat" && (
                  <Suspense fallback={<RouteFallback label="Loading case chat..." />}>
                    <CaseChat
                      caseId={selectedCase.id}
                      caseLabel={`${(selectedCase.custom_condition || selectedCase.condition || "case").replace(/_/g, " ")} · Case #${selectedCase.id}`}
                      socketEvent={selectedCaseSocketEvent}
                    />
                  </Suspense>
                )}

                {panelMode === "call" && (
                  <Suspense fallback={<RouteFallback label="Loading call controls..." />}>
                    <CallPanel
                      socket={selectedCaseSocket}
                      caseId={selectedCase.id}
                      role="hospital"
                      remoteLabel="Unit 7 — Paramedic"
                      onClose={() => setPanelMode(null)}
                    />
                  </Suspense>
                )}
              </div>
            </div>
          )}

          {actionError && (
            <div className="bg-[#FFF0F0] border border-[#FFCDD2] rounded-lg px-4 py-3 text-[#EE3B3B] text-[13px] mb-4">
              {actionError}
            </div>
          )}

          {/* Cases */}
          {loading ? (
            <div className="flex justify-center py-24">
              <div className="w-10 h-10 border-4 border-[#1A78F2] border-t-transparent rounded-full animate-spin" />
            </div>
          ) : cases.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-[#737A8F]">
              <div className="w-4 h-4 rounded-full bg-[#17B86B] animate-pulse mb-4" />
              <p className="text-[16px]">No cases assigned yet — standing by</p>
            </div>
          ) : (
            <div className="flex flex-col gap-8">
              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-[16px] font-bold text-[#1A1E2E]">Incoming Cases</h2>
                  <span className="text-[12px] text-[#737A8F]">{incomingCases.length} awaiting response</span>
                </div>
                {incomingCases.length === 0 ? (
                  <div className="bg-white border border-[#F0F2F7] rounded-xl p-6 text-[13px] text-[#737A8F]">
                    No incoming dispatches awaiting hospital response.
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {incomingCases.map(c => {
                      const pct = Math.round((c.final_score||0)*100);
                      return (
                        <div key={c.id} className="bg-white rounded-xl border border-[#F0F2F7] overflow-hidden shadow-sm">
                          <div className="h-1 bg-[#EE3B3B]" />
                          <div className="flex items-center justify-between px-6 py-3 border-b border-[#F0F2F7] bg-gray-50">
                            <div className="flex items-center gap-2">
                              <span className="flex items-center gap-2 bg-[#FFEDED] text-[#EE3B3B] text-[10px] font-bold px-2.5 py-1 rounded-full">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#EE3B3B] animate-pulse" /> {fmtStatus(c.status)}
                              </span>
                              {c.assigned_hospital_name && (
                                <span className="text-[10px] font-semibold text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-2.5 py-1">
                                  🏥 {c.assigned_hospital_name}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-4">
                              <span className="font-mono text-[13px] font-semibold text-[#737A8F]">Case #{c.id}</span>
                              <span className="text-[12px] text-[#C7CCD9]">{timeAgo(c.created_at)}</span>
                            </div>
                          </div>
                          <div className="px-6 py-4 border-b border-[#F0F2F7]">
                            <p className="text-[22px] font-extrabold text-[#EE3B3B] uppercase mb-2">
                              {(c.custom_condition || c.condition)?.replace(/_/g, " ")}
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {c.equipment_needed?.length > 0
                                ? c.equipment_needed.map(eq => (
                                    <span key={eq} className="bg-[#E8FDF2] text-[#17B86B] text-[11px] font-bold px-3 py-1 rounded-md uppercase">
                                      {eq.replace(/_/g, " ")}
                                    </span>
                                  ))
                                : <span className="text-[13px] text-[#C7CCD9]">No equipment specified</span>
                              }
                            </div>
                          </div>
                          <div className="px-6 py-4 flex items-center gap-6">
                            <div className="flex items-center gap-3 flex-1">
                              <span className="text-[13px] font-semibold text-[#737A8F]">Score</span>
                              <span className="text-[16px] font-extrabold px-2 py-0.5 rounded-lg text-[13px]"
                                style={{ color: scoreColor(pct), backgroundColor: scoreBg(pct) }}>
                                {pct}%
                              </span>
                              <div className="flex-1 h-2 bg-[#F0F2F7] rounded-full overflow-hidden">
                                <div className="h-full rounded-full transition-all duration-700"
                                  style={{ width:`${pct}%`, backgroundColor: scoreColor(pct) }} />
                              </div>
                            </div>
                            <div className="flex gap-6 text-center">
                              <div><p className="text-[16px] font-bold text-[#1A1E2E]">{c.severity_score ?? "N/A"}</p><p className="text-[11px] text-[#737A8F]">Severity</p></div>
                              <div><p className="text-[16px] font-bold text-[#1A1E2E]">{c.eta_minutes ?? "—"} min</p><p className="text-[11px] text-[#737A8F]">ETA</p></div>
                            </div>
                          </div>
                          <div className="px-6 pb-5 flex items-center gap-3">
                            <button
                              onClick={() => openPanel(c, "chat")}
                              className="bg-white border border-[#BDD6FF] text-[#1A78F2] font-bold text-[13px] px-4 py-3 rounded-xl transition"
                            >
                              Chat
                            </button>
                            <button
                              onClick={() => openPanel(c, "call")}
                              className="bg-[#1A78F2] hover:bg-[#1259C8] text-white font-bold text-[13px] px-4 py-3 rounded-xl transition"
                            >
                              Call
                            </button>
                            <button
                              onClick={() => acceptCase(c.id)}
                              disabled={Boolean(actionLoading[c.id])}
                              className="bg-[#17B86B] hover:bg-[#12965A] disabled:opacity-60 text-white font-bold text-[13px] px-5 py-3 rounded-xl transition"
                            >
                              {actionLoading[c.id] === "accept" ? "Accepting..." : "Accept"}
                            </button>
                            <input
                              value={declineReasons[c.id] || ""}
                              onChange={e => setDeclineReasons(prev => ({ ...prev, [c.id]: e.target.value }))}
                              placeholder="Decline reason"
                              className="flex-1 px-3 py-3 border border-[#E2E6F0] rounded-xl text-[13px] outline-none"
                            />
                            <button
                              onClick={() => declineCase(c.id)}
                              disabled={Boolean(actionLoading[c.id])}
                              className="bg-white border border-[#FFCDD2] hover:bg-[#FFF0F0] disabled:opacity-60 text-[#EE3B3B] font-bold text-[13px] px-5 py-3 rounded-xl transition"
                            >
                              {actionLoading[c.id] === "decline" ? "Declining..." : "Decline"}
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              <section>
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-[16px] font-bold text-[#1A1E2E]">Active Cases</h2>
                  <span className="text-[12px] text-[#737A8F]">{activeCases.length} in progress</span>
                </div>
                {activeCases.length === 0 ? (
                  <div className="bg-white border border-[#F0F2F7] rounded-xl p-6 text-[13px] text-[#737A8F]">
                    Accepted cases will appear here.
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {activeCases.map(c => {
                const pct = Math.round((c.final_score||0)*100);
                return (
                  <div key={c.id} className="bg-white rounded-xl border border-[#F0F2F7] overflow-hidden shadow-sm">
                    <div className="h-1 bg-[#EE3B3B]" />
                    {/* Header row */}
                    <div className="flex items-center justify-between px-6 py-3 border-b border-[#F0F2F7] bg-gray-50">
                      <div className="flex items-center gap-2">
                        <span className="flex items-center gap-2 bg-[#FFEDED] text-[#EE3B3B] text-[10px] font-bold px-2.5 py-1 rounded-full">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#1A78F2]" /> {fmtStatus(c.status)}
                        </span>
                        {c.assigned_hospital_name && (
                          <span className="text-[10px] font-semibold text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-2.5 py-1">
                            🏥 {c.assigned_hospital_name}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-[13px] font-semibold text-[#737A8F]">Case #{c.id}</span>
                        <span className="text-[12px] text-[#C7CCD9]">{timeAgo(c.created_at)}</span>
                      </div>
                    </div>
                    {/* Condition */}
                    <div className="px-6 py-4 border-b border-[#F0F2F7]">
                      <p className="text-[22px] font-extrabold text-[#EE3B3B] uppercase mb-2">
                        {(c.custom_condition || c.condition)?.replace(/_/g, " ")}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {c.equipment_needed?.length > 0
                          ? c.equipment_needed.map(eq => (
                              <span key={eq} className="bg-[#E8FDF2] text-[#17B86B] text-[11px] font-bold px-3 py-1 rounded-md uppercase">
                                {eq.replace(/_/g, " ")}
                              </span>
                            ))
                          : <span className="text-[13px] text-[#C7CCD9]">No equipment specified</span>
                        }
                      </div>
                    </div>
                    {/* Stats + Button */}
                    <div className="px-6 py-4 flex items-center gap-6">
                      <div className="flex items-center gap-3 flex-1">
                        <span className="text-[13px] font-semibold text-[#737A8F]">Score</span>
                        <span className="text-[16px] font-extrabold px-2 py-0.5 rounded-lg text-[13px]"
                          style={{ color: scoreColor(pct), backgroundColor: scoreBg(pct) }}>
                          {pct}%
                        </span>
                        <div className="flex-1 h-2 bg-[#F0F2F7] rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all duration-700"
                            style={{ width:`${pct}%`, backgroundColor: scoreColor(pct) }} />
                        </div>
                      </div>
                      <div className="flex gap-6 text-center">
                        <div><p className="text-[16px] font-bold text-[#1A1E2E]">{c.distance_km} km</p><p className="text-[11px] text-[#737A8F]">Distance</p></div>
                        <div><p className="text-[16px] font-bold text-[#1A1E2E]">{c.eta_minutes} min</p><p className="text-[11px] text-[#737A8F]">ETA</p></div>
                      </div>
                      <button
                        onClick={() => openPanel(c, "chat")}
                        className="bg-white border border-[#BDD6FF] text-[#1A78F2] font-bold text-[13px] px-4 py-3 rounded-xl transition"
                      >
                        Chat
                      </button>
                      <button
                        onClick={() => openPanel(c, "call")}
                        className="bg-[#1A78F2] hover:bg-[#1259C8] text-white font-bold text-[13px] px-4 py-3 rounded-xl transition"
                      >
                        Call
                      </button>
                      <button
                        onClick={() => navigate(`/hospital/track/${c.id}`)}
                        className="bg-[#1A78F2] hover:bg-[#1259C8] text-white font-bold text-[13px] px-6 py-3 rounded-xl transition"
                      >
                        🚑 Track Ambulance
                      </button>
                    </div>
                  </div>
                );
                    })}
                  </div>
                )}
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
