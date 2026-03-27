// frontend/src/pages/AdminDashboard.jsx
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";

export default function AdminDashboard() {
  const navigate  = useNavigate();
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [time,    setTime]    = useState(new Date());

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const fetchStats = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get("/api/cases/admin/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(res.data);
    } catch { } finally { setLoading(false); }
  };

  useEffect(() => {
    fetchStats();
    const t = setInterval(fetchStats, 15000);
    return () => clearInterval(t);
  }, []);

  const maxBeds    = data ? Math.max(...data.districts.map(d => d.beds), 1) : 1;
  const scoreColor = s => s > 0.7 ? "#17B86B" : s > 0.4 ? "#FFB21A" : "#EE3B3B";
  const navItems   = ["📊  Overview","🏥  Hospitals","🚑  Dispatches","🤖  ML Engine","⚙️  Settings"];

  return (
    <div className="flex h-screen bg-[#F7F7FC] font-['Inter',sans-serif] overflow-hidden">

      {/* ── Sidebar ── */}
      <aside className="w-[240px] bg-[#0D1830] flex-shrink-0 flex flex-col relative">
        <div className="absolute left-0 top-0 w-[3px] h-full bg-[#1A78F2]" />
        <div className="px-7 pt-7 pb-5">
          <p className="text-[18px] font-bold text-white">MediRoute</p>
          <p className="text-[12px] text-[#737A8F]">Admin Control</p>
        </div>
        <nav className="flex flex-col gap-1 px-3">
          {navItems.map((item, i) => (
            <div key={i} className={`px-4 py-3 rounded-xl text-[14px] cursor-pointer transition
              ${i===0 ? "bg-[#172954] text-white font-semibold" : "text-[#737A8F] hover:text-white"}`}>
              {item}
            </div>
          ))}
        </nav>
        <div className="mt-auto px-7 pb-6">
          <p className="text-[12px] text-[#737A8F]">admin@test.com</p>
          <button onClick={() => { localStorage.clear(); navigate("/login"); }}
            className="mt-1 text-[12px] text-[#737A8F] hover:text-white transition">
            Sign out →
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-y-auto">
        {/* Top bar */}
        <div className="bg-white border-b border-[#F0F2F7] h-16 flex items-center justify-between px-8">
          <h1 className="text-[22px] font-bold text-[#1A1E2E]">System Overview</h1>
          <div className="flex items-center gap-4">
            <span className="text-[12px] text-[#737A8F]">{time.toLocaleTimeString()} IST</span>
            <span className={`flex items-center gap-2 text-[11px] font-bold px-3 py-1.5 rounded-full ${data ? "bg-[#E8FDF2] text-[#17B86B]" : "bg-[#FFF8E0] text-[#FFB21A]"}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              {data ? "LIVE · ↻ 15s" : "CONNECTING..."}
            </span>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-24">
            <div className="w-10 h-10 border-4 border-[#1A78F2] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : data && (
          <div className="p-8 flex flex-col gap-6">

            {/* Stat Cards */}
            <div className="grid grid-cols-4 gap-4">
              {[
                { val: data.total_hospitals,  label: "Hospitals Online",  sub: `${data.accepting_hospitals} accepting`, accent: "#1A78F2" },
                { val: data.total_beds.toLocaleString(), label: "Total Beds", sub: "Across Uttarakhand", accent: "#17B86B" },
                { val: data.total_icu.toLocaleString(),  label: "ICU Beds",   sub: "Critical care", accent: "#FFB21A" },
                { val: data.total_cases,      label: "Total Dispatches", sub: `${data.cases_last_24h} in last 24h`, accent: "#EE3B3B" },
              ].map(({ val, label, sub, accent }) => (
                <div key={label} className="bg-white rounded-xl border border-[#F0F2F7] overflow-hidden">
                  <div className="h-1" style={{ backgroundColor: accent }} />
                  <div className="p-5">
                    <p className="text-[32px] font-extrabold text-[#1A1E2E]">{val}</p>
                    <p className="text-[13px] font-semibold text-[#1A1E2E] mt-1">{label}</p>
                    <p className="text-[11px] text-[#737A8F]">{sub}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Middle row */}
            <div className="grid grid-cols-2 gap-6">
              {/* District Breakdown */}
              <div className="bg-white rounded-xl border border-[#F0F2F7] p-6">
                <p className="text-[15px] font-bold text-[#1A1E2E] mb-5">District Capacity</p>
                <div className="flex flex-col gap-4">
                  {data.districts.map(d => (
                    <div key={d.name} className="flex items-center gap-3">
                      <p className="text-[12px] font-semibold text-[#1A1E2E] w-20 flex-shrink-0">{d.name}</p>
                      <div className="flex-1 h-2.5 bg-[#F0F2F7] rounded-full overflow-hidden">
                        <div className="h-full bg-[#1A78F2] rounded-full transition-all"
                          style={{ width: `${(d.beds / maxBeds) * 100}%` }} />
                      </div>
                      <span className="text-[11px] text-[#737A8F] w-16 text-right">{d.beds} beds</span>
                      <span className="text-[11px] text-[#FFB21A] w-14 text-right">{d.icu} ICU</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Recent Dispatches */}
              <div className="bg-white rounded-xl border border-[#F0F2F7] p-6">
                <p className="text-[15px] font-bold text-[#1A1E2E] mb-5">Recent Dispatches</p>
                {data.recent_cases.length === 0 ? (
                  <p className="text-[13px] text-[#C7CCD9] text-center py-8">No dispatches yet</p>
                ) : (
                  <div className="flex flex-col gap-0">
                    {data.recent_cases.slice(0, 6).map((c, i) => (
                      <div key={c.id} className={`flex items-center gap-3 px-3 py-3 rounded-lg text-[12px] ${i%2===0 ? "bg-[#F7F7FC]" : ""}`}>
                        <span className="text-[#C7CCD9] font-mono w-8">#{c.id}</span>
                        <span className="text-[#C7CCD9] w-12">{c.created_at}</span>
                        <span className="text-[#1A1E2E] font-semibold flex-1 truncate">{c.hospital_name}</span>
                        <span className="text-[#737A8F] uppercase text-[10px] w-20 truncate">{c.condition?.replace("_"," ")}</span>
                        <span className="font-bold w-10 text-right" style={{ color: scoreColor(c.score) }}>
                          {Math.round(c.score*100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* ML Engine Status */}
            <div className="bg-white rounded-xl border border-[#F0F2F7] overflow-hidden">
              <div className="flex items-center gap-3 border-b border-[#F0F2F7] px-6 py-4">
                <div className="w-1 h-6 bg-[#1A78F2] rounded-full" />
                <p className="text-[15px] font-bold text-[#1A1E2E]">ML Engine Status</p>
                <span className="ml-auto bg-[#E8FDF2] text-[#17B86B] text-[11px] font-bold px-3 py-1 rounded-full">● OPERATIONAL</span>
              </div>
              <div className="grid grid-cols-6 divide-x divide-[#F0F2F7]">
                {[
                  ["RandomForest",   "Algorithm"],
                  ["112,800",        "Training Samples"],
                  ["15",             "Input Features"],
                  ["188",            "Hospitals Scored"],
                  ["Auto-tuned",     "Threshold"],
                  ["Rule-based",     "Fallback"],
                ].map(([val, label]) => (
                  <div key={label} className="p-5">
                    <p className="text-[16px] font-bold text-[#1A78F2]">{val}</p>
                    <p className="text-[11px] text-[#737A8F] mt-1">{label}</p>
                  </div>
                ))}
              </div>
            </div>

          </div>
        )}
      </main>
    </div>
  );
}
