import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function HospitalDashboard() {
  const navigate  = useNavigate();
  const [cases,   setCases]   = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchCases = async () => {
    try {
      const token = localStorage.getItem("token");
      if (!token) { navigate("/login"); return; }
      const res = await axios.get("/api/cases/hospital", {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = Array.isArray(res.data) ? res.data : (res.data.items || []);
      setCases(data.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)));
    } catch { } finally { setLoading(false); }
  };

  useEffect(() => {
    fetchCases();
    const t = setInterval(fetchCases, 10000);
    return () => clearInterval(t);
  }, []);

  const todayCount  = cases.filter(c => {
    const d = new Date(c.created_at), now = new Date();
    return d.getDate()===now.getDate() && d.getMonth()===now.getMonth() && d.getFullYear()===now.getFullYear();
  }).length;
  const avgScore    = cases.length ? Math.round(cases.reduce((a, c) => a + (c.final_score||0), 0) / cases.length * 100) : 0;
  const timeAgo     = ds => { const m = Math.round((new Date()-new Date(ds))/60000); return m===0?"Just now":`${m}m ago`; };
  const scoreColor  = s => s > 70 ? "#17B86B" : s > 50 ? "#FFB21A" : "#EE3B3B";
  const scoreBg     = s => s > 70 ? "#E8FDF2" : s > 50 ? "#FFF8E0" : "#FFEDED";

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
          <p className="text-[12px] text-[#737A8F]">Roorkee · ID #28</p>
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
                {cases.length} INCOMING
              </span>
            )}
            <span className="text-[11px] text-[#737A8F] bg-[#F0F2F7] px-3 py-1.5 rounded-full">↻ Live · 10s</span>
          </div>
        </div>

        <div className="p-8">
          {/* Stats row */}
          <div className="grid grid-cols-4 gap-4 mb-8">
            {[
              { val: todayCount,    label: "Cases Today",    accent: "#EE3B3B" },
              { val: cases.length,  label: "Active Cases",   accent: "#1A78F2" },
              { val: `${avgScore}%`,label: "Avg ML Score",   accent: "#17B86B" },
              { val: "28",          label: "Beds Available", accent: "#FFB21A" },
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
            <div className="flex flex-col gap-4">
              {cases.map(c => {
                const pct = Math.round((c.final_score||0)*100);
                return (
                  <div key={c.id} className="bg-white rounded-xl border border-[#F0F2F7] overflow-hidden shadow-sm">
                    <div className="h-1 bg-[#EE3B3B]" />
                    {/* Header row */}
                    <div className="flex items-center justify-between px-6 py-3 border-b border-[#F0F2F7] bg-gray-50">
                      <span className="flex items-center gap-2 bg-[#FFEDED] text-[#EE3B3B] text-[10px] font-bold px-2.5 py-1 rounded-full">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#EE3B3B] animate-pulse" /> INCOMING
                      </span>
                      <div className="flex items-center gap-4">
                        <span className="font-mono text-[13px] font-semibold text-[#737A8F]">Case #{c.id}</span>
                        <span className="text-[12px] text-[#C7CCD9]">{timeAgo(c.created_at)}</span>
                      </div>
                    </div>
                    {/* Condition */}
                    <div className="px-6 py-4 border-b border-[#F0F2F7]">
                      <p className="text-[22px] font-extrabold text-[#EE3B3B] uppercase mb-2">
                        {c.condition?.replace(/_/g, " ")}
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
        </div>
      </main>
    </div>
  );
}
