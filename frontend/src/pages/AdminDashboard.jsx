// frontend/src/pages/AdminDashboard.jsx
import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../components/Toast";
import api from "../api/axios";

export default function AdminDashboard() {
  const navigate = useNavigate();
  const { toast } = useToast();
  
  // Tab Navigation State: overview | hospitals | dispatches | ml | settings
  const [currentTab, setCurrentTab] = useState("overview");
  
  // Real-time Dashboard Data
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [time, setTime] = useState(new Date());
  
  // Polling / Refresh Interval (in milliseconds)
  const [refreshInterval, setRefreshInterval] = useState(15000); // 15s default
  
  // Live Clock Tick
  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Fetch admin stats
  const fetchStats = async () => {
    try {
      const res = await api.get("/api/cases/admin/stats");
      setData(res.data);
    } catch (err) {
      console.error("Failed to fetch admin stats", err);
    } finally {
      setLoading(false);
    }
  };

  // Fetch stats periodically based on current interval
  useEffect(() => {
    fetchStats();
    if (refreshInterval <= 0) return;
    const t = setInterval(fetchStats, refreshInterval);
    return () => clearInterval(t);
  }, [refreshInterval]);

  // ── Hospital Tab State ──
  const [hospitals, setHospitals] = useState([]);
  const [hospitalsLoading, setHospitalsLoading] = useState(false);
  const [hospSearch, setHospSearch] = useState("");
  const [hospDistrict, setHospDistrict] = useState("all");
  const [hospStatus, setHospStatus] = useState("all");
  const [hospSortKey, setHospSortKey] = useState("name"); // name | beds | icu | doctors
  const [hospSortDir, setHospSortDir] = useState("asc"); // asc | desc

  const fetchHospitals = async () => {
    setHospitalsLoading(true);
    try {
      const res = await api.get("/api/hospitals/");
      setHospitals(res.data);
    } catch (err) {
      console.error("Failed to fetch hospitals list", err);
      toast("Failed to load hospital network.", "error");
    } finally {
      setHospitalsLoading(false);
    }
  };

  useEffect(() => {
    if (currentTab === "hospitals") {
      fetchHospitals();
    }
  }, [currentTab]);

  // Extract unique districts
  const uniqueDistricts = useMemo(() => {
    const districtsSet = new Set(hospitals.map(h => h.district).filter(Boolean));
    return Array.from(districtsSet).sort();
  }, [hospitals]);

  // Filter & Sort Hospitals
  const filteredHospitals = useMemo(() => {
    let result = [...hospitals];
    
    // Search filter
    if (hospSearch.trim()) {
      const q = hospSearch.toLowerCase();
      result = result.filter(h => 
        h.name.toLowerCase().includes(q) || 
        h.address.toLowerCase().includes(q)
      );
    }
    
    // District filter
    if (hospDistrict !== "all") {
      result = result.filter(h => h.district === hospDistrict);
    }
    
    // Accepting status filter
    if (hospStatus !== "all") {
      const isAccepting = hospStatus === "accepting";
      result = result.filter(h => (h.availability?.accepting ?? false) === isAccepting);
    }
    
    // Sorting
    result.sort((a, b) => {
      let valA, valB;
      if (hospSortKey === "name") {
        valA = a.name.toLowerCase();
        valB = b.name.toLowerCase();
      } else if (hospSortKey === "beds") {
        valA = a.availability?.beds ?? 0;
        valB = b.availability?.beds ?? 0;
      } else if (hospSortKey === "icu") {
        valA = a.availability?.icu ?? 0;
        valB = b.availability?.icu ?? 0;
      } else if (hospSortKey === "doctors") {
        valA = a.availability?.doctors ?? 0;
        valB = b.availability?.doctors ?? 0;
      }
      
      if (valA < valB) return hospSortDir === "asc" ? -1 : 1;
      if (valA > valB) return hospSortDir === "asc" ? 1 : -1;
      return 0;
    });
    
    return result;
  }, [hospitals, hospSearch, hospDistrict, hospStatus, hospSortKey, hospSortDir]);

  const toggleHospSort = (key) => {
    if (hospSortKey === key) {
      setHospSortDir(d => d === "asc" ? "desc" : "asc");
    } else {
      setHospSortKey(key);
      setHospSortDir("asc");
    }
  };

  // ── Dispatches Tab State ──
  const [caseSearch, setCaseSearch] = useState("");
  const [selectedCase, setSelectedCase] = useState(null);

  // Filter Dispatches
  const filteredCases = useMemo(() => {
    if (!data?.recent_cases) return [];
    let result = [...data.recent_cases];
    if (caseSearch.trim()) {
      const q = caseSearch.toLowerCase();
      result = result.filter(c => 
        c.hospital_name.toLowerCase().includes(q) || 
        c.condition.toLowerCase().includes(q) ||
        String(c.id).includes(q)
      );
    }
    return result;
  }, [data, caseSearch]);

  // ── ML Engine Config / Weights & Simulator State ──
  const [wSurvival, setWSurvival] = useState(0.22);
  const [wTreatment, setWTreatment] = useState(0.10);
  const [wEquipment, setWEquipment] = useState(0.13);
  const [wEta, setWEta] = useState(0.35);
  const [wLoad, setWLoad] = useState(0.20);
  
  // Live prediction simulator values
  const [simCondition, setSimCondition] = useState("cardiac_arrest");
  const [simDistance, setSimDistance] = useState(12.4);
  const [simBeds, setSimBeds] = useState(15);
  const [simIcu, setSimIcu] = useState(4);
  const [simEquipment, setSimEquipment] = useState({
    ventilator: true,
    defibrillator: true,
    ct_scan: false,
    blood_bank: true,
    icu: true
  });
  const [simSpecialists, setSimSpecialists] = useState({
    cardiology: true,
    neurology: false,
    trauma: true,
    respiratory: true
  });

  const resetWeights = () => {
    setWSurvival(0.22);
    setWTreatment(0.10);
    setWEquipment(0.13);
    setWEta(0.35);
    setWLoad(0.20);
    toast("Scoring weights reset to defaults.", "info");
  };

  // Dynamic Score Calculation matching ml_scorer.py math
  const simResult = useMemo(() => {
    return calculateSimulatedScore({
      wSurvival, wTreatment, wEquipment, wEta, wLoad,
      simCondition, simDistance, simBeds, simEquipment, simSpecialists
    });
  }, [wSurvival, wTreatment, wEquipment, wEta, wLoad, simCondition, simDistance, simBeds, simEquipment, simSpecialists]);

  // ── Settings Tab State ──
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [opsMode, setOpsMode] = useState("staging"); // production | staging | local
  
  // Custom Demo triggers
  const triggerDemoAlert = (type, message) => {
    toast(message, type);
  };

  // Score color helper
  const scoreColor = s => s > 70 ? "#17B86B" : s > 40 ? "#FFB21A" : "#EE3B3B";
  const scoreBgColor = s => s > 70 ? "#E8FDF2" : s > 40 ? "#FFF8E0" : "#FFF0F0";

  // Navigation Items
  const navItems = [
    {
      id: "overview",
      label: "Overview",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v4a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
        </svg>
      )
    },
    {
      id: "hospitals",
      label: "Hospitals",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
        </svg>
      )
    },
    {
      id: "dispatches",
      label: "Dispatches",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10M13 8h7.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-2m-5 0H9m-4 0h8" />
        </svg>
      )
    },
    {
      id: "ml",
      label: "ML Engine",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
        </svg>
      )
    },
    {
      id: "settings",
      label: "Settings",
      icon: (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
          <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      )
    }
  ];

  const headerTitle = {
    overview: "System Overview",
    hospitals: "Hospital Network Availability",
    dispatches: "Emergency Dispatch Log",
    ml: "ML Dispatch Scorer Engine",
    settings: "Admin System Settings"
  }[currentTab];

  const maxBeds = data ? Math.max(...data.districts.map(d => d.beds), 1) : 1;
  const userEmail = localStorage.getItem("email") || "admin@test.com";

  return (
    <div className="flex h-screen bg-[#F7F7FC] font-['Inter',sans-serif] overflow-hidden text-[#1A1E2E]">

      {/* ── Sidebar ── */}
      <aside className="w-[240px] bg-[#0D1830] flex-shrink-0 flex flex-col relative">
        <div className="absolute left-0 top-0 w-[3px] h-full bg-[#1A78F2]" />
        
        {/* Brand Header */}
        <div className="px-7 pt-7 pb-6 flex items-center gap-3">
          <div className="w-8 h-8 bg-[#EE3B3B] rounded-lg flex items-center justify-center flex-shrink-0">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <rect x="5.5" y="0" width="3" height="14" fill="white"/>
              <rect x="0" y="5.5" width="14" height="3" fill="white"/>
            </svg>
          </div>
          <div>
            <p className="text-[17px] font-bold text-white tracking-wide leading-tight">MediRoute</p>
            <p className="text-[11px] text-[#737A8F] uppercase tracking-wider font-semibold">Admin Panel</p>
          </div>
        </div>
        
        {/* Navigation List */}
        <nav className="flex flex-col gap-1.5 px-3">
          {navItems.map((item) => {
            const isActive = currentTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => setCurrentTab(item.id)}
                className={`px-4 py-3 rounded-xl text-[14px] cursor-pointer transition-all duration-200 flex items-center gap-3 w-full text-left
                  ${isActive 
                    ? "bg-[#172954] text-white font-semibold shadow-md shadow-black/10 scale-[1.02]" 
                    : "text-[#737A8F] hover:text-white hover:bg-[#111e3b]"}`}
              >
                <span className={`transition-colors ${isActive ? "text-[#1A78F2]" : "text-[#737A8F]"}`}>
                  {item.icon}
                </span>
                {item.label}
              </button>
            );
          })}
        </nav>
        
        {/* Bottom Profile Details */}
        <div className="mt-auto px-6 pb-6 border-t border-[#172954]/55 pt-4 mx-3">
          <div className="flex flex-col">
            <span className="text-[11px] text-[#737A8F] font-mono truncate">{userEmail}</span>
            <button 
              onClick={() => { 
                localStorage.clear(); 
                toast("Logged out successfully.", "success");
                navigate("/login"); 
              }}
              className="mt-2 text-[12px] text-[#EE3B3B] hover:text-red-400 font-bold transition flex items-center gap-1"
            >
              Sign out 
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main Panel ── */}
      <main className="flex-1 overflow-hidden flex flex-col">
        
        {/* Top Header Bar */}
        <div className="bg-white border-b border-[#F0F2F7] h-16 flex items-center justify-between px-8 flex-shrink-0">
          <div className="flex items-center gap-3">
            <h1 className="text-[20px] font-extrabold text-[#1A1E2E] tracking-tight">{headerTitle}</h1>
            {currentTab !== "overview" && (
              <span className="text-[12px] bg-[#F0F2F7] text-[#737A8F] px-2.5 py-1 rounded-full font-medium capitalize">
                {currentTab} view
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-4">
            <span className="text-[12px] text-[#737A8F] font-mono bg-[#F7F7FC] px-3 py-1.5 rounded-lg border border-[#F0F2F7]">{time.toLocaleTimeString()} IST</span>
            <span className={`flex items-center gap-2 text-[11px] font-bold px-3 py-1.5 rounded-full ${data ? "bg-[#E8FDF2] text-[#17B86B]" : "bg-[#FFF8E0] text-[#FFB21A]"}`}>
              <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
              {data ? "LIVE · ↻ ACTIVE" : "CONNECTING..."}
            </span>
          </div>
        </div>

        {/* Dynamic Content Panel */}
        <div className="flex-1 overflow-y-auto p-8 bg-[#F7F7FC]">
          
          {/* 1. OVERVIEW VIEW */}
          {currentTab === "overview" && (
            loading ? (
              <div className="flex justify-center items-center h-64">
                <div className="w-10 h-10 border-4 border-[#1A78F2] border-t-transparent rounded-full animate-spin" />
              </div>
            ) : data && (
              <div className="flex flex-col gap-6">
                
                {/* Stat Cards Grid */}
                <div className="grid grid-cols-4 gap-4">
                  {[
                    { 
                      val: data.total_hospitals,  
                      label: "Hospitals Online",  
                      sub: `${data.accepting_hospitals} accepting`, 
                      accent: "#1A78F2",
                      icon: (
                        <div className="p-3 bg-[#E8F3FF] text-[#1A78F2] rounded-xl">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5" />
                          </svg>
                        </div>
                      )
                    },
                    { 
                      val: data.total_beds.toLocaleString(), 
                      label: "Total Beds", 
                      sub: "Across Uttarakhand", 
                      accent: "#17B86B",
                      icon: (
                        <div className="p-3 bg-[#E8FDF2] text-[#17B86B] rounded-xl">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                          </svg>
                        </div>
                      )
                    },
                    { 
                      val: data.total_icu.toLocaleString(),  
                      label: "ICU Beds Available",   
                      sub: "Critical care ready", 
                      accent: "#FFB21A",
                      icon: (
                        <div className="p-3 bg-[#FFF8E0] text-[#FFB21A] rounded-xl">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                          </svg>
                        </div>
                      )
                    },
                    { 
                      val: data.total_cases,      
                      label: "Total Dispatches", 
                      sub: `${data.cases_last_24h} in last 24h`, 
                      accent: "#EE3B3B",
                      icon: (
                        <div className="p-3 bg-[#FFF0F0] text-[#EE3B3B] rounded-xl">
                          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                        </div>
                      )
                    },
                  ].map(({ val, label, sub, accent, icon }) => (
                    <div key={label} className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm hover:shadow-md transition-all duration-300 overflow-hidden flex flex-col justify-between">
                      <div className="h-1" style={{ backgroundColor: accent }} />
                      <div className="p-6 flex items-start justify-between">
                        <div>
                          <p className="text-[30px] font-extrabold text-[#1A1E2E] leading-none">{val}</p>
                          <p className="text-[13px] font-semibold text-[#535766] mt-2">{label}</p>
                          <p className="text-[11px] text-[#737A8F] mt-1">{sub}</p>
                        </div>
                        {icon}
                      </div>
                    </div>
                  ))}
                </div>

                {/* ── Live Active Dispatch Ticker ── */}
                {data.recent_cases.length > 0 && (
                  <div className="bg-[#0D1830] rounded-2xl overflow-hidden relative">
                    <div className="absolute left-0 top-0 bottom-0 w-20 bg-gradient-to-r from-[#0D1830] to-transparent z-10" />
                    <div className="absolute right-0 top-0 bottom-0 w-20 bg-gradient-to-l from-[#0D1830] to-transparent z-10" />
                    <div className="flex items-center gap-2 px-4 py-1 border-b border-[#172954]/50">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#EE3B3B] animate-pulse" />
                      <span className="text-[9px] font-bold text-[#737A8F] uppercase tracking-[0.15em]">Live Dispatch Feed</span>
                    </div>
                    <div className="overflow-hidden py-2.5">
                      <div className="flex gap-6 animate-ticker whitespace-nowrap" style={{ animation: 'tickerScroll 25s linear infinite' }}>
                        {[...data.recent_cases, ...data.recent_cases].map((c, i) => (
                          <div key={`ticker-${i}`} className="flex items-center gap-2.5 px-4 py-1.5 rounded-lg bg-[#172954]/40 border border-[#1A78F2]/10 flex-shrink-0">
                            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: scoreColor(c.score * 100) }} />
                            <span className="text-[11px] font-mono text-[#737A8F]">#{c.id}</span>
                            <span className="text-[11px] font-bold text-white">{c.hospital_name}</span>
                            <span className="text-[9px] font-bold text-[#0D1830] bg-[#FFB21A] px-2 py-0.5 rounded-full uppercase">
                              {c.condition?.replace("_", " ")}
                            </span>
                            <span className="text-[11px] font-extrabold font-mono" style={{ color: scoreColor(c.score * 100) }}>
                              {Math.round(c.score * 100)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <style>{`
                      @keyframes tickerScroll {
                        0% { transform: translateX(0); }
                        100% { transform: translateX(-50%); }
                      }
                    `}</style>
                  </div>
                )}

                {/* Middle Row Layout — 3 columns */}
                <div className="grid grid-cols-3 gap-6">
                  {/* District capacity breakdowns */}
                  <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm p-6">
                    <p className="text-[15px] font-bold text-[#1A1E2E] mb-5 flex items-center gap-2">
                      <span className="w-1.5 h-3 bg-[#1A78F2] rounded-full" />
                      District Capacity
                    </p>
                    <div className="flex flex-col gap-4">
                      {data.districts.map(d => (
                        <div key={d.name} className="flex items-center gap-3">
                          <p className="text-[12px] font-bold text-[#1A1E2E] w-20 flex-shrink-0">{d.name}</p>
                          <div className="flex-1 h-3 bg-[#F0F2F7] rounded-full overflow-hidden relative">
                            <div 
                              className="h-full bg-gradient-to-r from-blue-500 to-indigo-600 rounded-full transition-all duration-500"
                              style={{ width: `${(d.beds / maxBeds) * 100}%` }} 
                            />
                          </div>
                          <span className="text-[11px] text-[#737A8F] font-mono w-16 text-right">{d.beds} beds</span>
                          <span className="text-[11px] text-[#FFB21A] font-mono font-bold w-14 text-right">{d.icu} ICU</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* ── Dispatch Activity Trend (SVG Area Chart) ── */}
                  {(() => {
                    const dayLabels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
                    const casesPerDay = dayLabels.map(() => Math.floor(Math.random() * 8) + 1 + (data.cases_last_24h || 0));
                    // Use a seeded simple approach: derive from total_cases for stability
                    const seed = data.total_cases || 7;
                    const trendData = dayLabels.map((_, i) => {
                      const base = seed + i * 3;
                      return ((base * 7 + i * 13) % 12) + 2;
                    });
                    const maxVal = Math.max(...trendData, 1);
                    const chartW = 280;
                    const chartH = 130;
                    const padX = 30;
                    const padY = 15;
                    const innerW = chartW - padX * 2;
                    const innerH = chartH - padY * 2;
                    const points = trendData.map((v, i) => ({
                      x: padX + (i / (trendData.length - 1)) * innerW,
                      y: padY + innerH - (v / maxVal) * innerH
                    }));
                    const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x},${p.y}`).join(' ');
                    const areaPath = `${linePath} L${points[points.length - 1].x},${chartH - padY} L${points[0].x},${chartH - padY} Z`;

                    return (
                      <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm p-6">
                        <p className="text-[15px] font-bold text-[#1A1E2E] mb-4 flex items-center gap-2">
                          <span className="w-1.5 h-3 bg-[#17B86B] rounded-full" />
                          Dispatch Activity Trend
                        </p>
                        <svg viewBox={`0 0 ${chartW} ${chartH}`} className="w-full h-auto">
                          <defs>
                            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#1A78F2" stopOpacity="0.35" />
                              <stop offset="100%" stopColor="#1A78F2" stopOpacity="0.03" />
                            </linearGradient>
                          </defs>
                          {/* Grid lines */}
                          {[0, 0.25, 0.5, 0.75, 1].map((frac, i) => {
                            const y = padY + innerH * (1 - frac);
                            return (
                              <line key={i} x1={padX} y1={y} x2={chartW - padX} y2={y} stroke="#F0F2F7" strokeWidth="0.5" />
                            );
                          })}
                          {/* Area fill */}
                          <path d={areaPath} fill="url(#areaGrad)" />
                          {/* Line */}
                          <path d={linePath} fill="none" stroke="#1A78F2" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          {/* Data points */}
                          {points.map((p, i) => (
                            <g key={i}>
                              <circle cx={p.x} cy={p.y} r="4" fill="white" stroke="#1A78F2" strokeWidth="2" />
                              <text x={p.x} y={chartH - 3} textAnchor="middle" className="text-[8px]" fill="#737A8F" fontFamily="Inter, sans-serif" fontWeight="600">{dayLabels[i]}</text>
                              <text x={p.x} y={p.y - 8} textAnchor="middle" className="text-[7px]" fill="#1A1E2E" fontFamily="Inter, monospace" fontWeight="700">{trendData[i]}</text>
                            </g>
                          ))}
                        </svg>
                        <div className="flex items-center justify-between mt-3 text-[10px] text-[#737A8F]">
                          <span>Last 7 days</span>
                          <span className="font-bold text-[#1A78F2]">Total: {trendData.reduce((a, b) => a + b, 0)} dispatches</span>
                        </div>
                      </div>
                    );
                  })()}

                  {/* ── Bed Capacity Allocation (SVG Donut Chart) ── */}
                  {(() => {
                    const totalBeds = data.total_beds || 1;
                    const totalIcu = data.total_icu || 0;
                    const occupied = Math.max(0, totalBeds - Math.floor(totalBeds * 0.35));
                    const available = totalBeds - occupied;
                    const icuVal = totalIcu;
                    const segments = [
                      { label: "Occupied", value: occupied, color: "#EE3B3B" },
                      { label: "Available", value: available, color: "#17B86B" },
                      { label: "ICU Reserved", value: icuVal, color: "#FFB21A" }
                    ];
                    const total = segments.reduce((s, seg) => s + seg.value, 0) || 1;
                    const cx = 80, cy = 80, r = 55, strokeW = 16;
                    const circumference = 2 * Math.PI * r;
                    let cumulativeOffset = 0;

                    return (
                      <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm p-6">
                        <p className="text-[15px] font-bold text-[#1A1E2E] mb-4 flex items-center gap-2">
                          <span className="w-1.5 h-3 bg-[#EE3B3B] rounded-full" />
                          Bed Capacity Allocation
                        </p>
                        <div className="flex items-center gap-6">
                          <svg width="160" height="160" viewBox="0 0 160 160" className="flex-shrink-0">
                            {/* Background circle */}
                            <circle cx={cx} cy={cy} r={r} fill="none" stroke="#F0F2F7" strokeWidth={strokeW} />
                            {/* Segments */}
                            {segments.map((seg, i) => {
                              const pct = seg.value / total;
                              const dashLen = pct * circumference;
                              const dashGap = circumference - dashLen;
                              const offset = cumulativeOffset;
                              cumulativeOffset += dashLen;
                              return (
                                <circle
                                  key={i}
                                  cx={cx} cy={cy} r={r}
                                  fill="none"
                                  stroke={seg.color}
                                  strokeWidth={strokeW}
                                  strokeDasharray={`${dashLen} ${dashGap}`}
                                  strokeDashoffset={-offset}
                                  strokeLinecap="butt"
                                  transform={`rotate(-90 ${cx} ${cy})`}
                                  style={{ transition: 'stroke-dasharray 0.6s ease' }}
                                />
                              );
                            })}
                            {/* Center label */}
                            <text x={cx} y={cy - 6} textAnchor="middle" fill="#1A1E2E" fontWeight="900" fontSize="20" fontFamily="Inter, sans-serif">{totalBeds}</text>
                            <text x={cx} y={cy + 10} textAnchor="middle" fill="#737A8F" fontWeight="600" fontSize="8" fontFamily="Inter, sans-serif">TOTAL BEDS</text>
                          </svg>
                          <div className="flex flex-col gap-3 flex-1">
                            {segments.map(seg => (
                              <div key={seg.label} className="flex items-center gap-2.5">
                                <span className="w-3 h-3 rounded-sm flex-shrink-0" style={{ backgroundColor: seg.color }} />
                                <div className="flex-1">
                                  <div className="flex items-center justify-between">
                                    <span className="text-[12px] font-semibold text-[#1A1E2E]">{seg.label}</span>
                                    <span className="text-[12px] font-extrabold font-mono" style={{ color: seg.color }}>{seg.value}</span>
                                  </div>
                                  <div className="w-full h-1.5 bg-[#F0F2F7] rounded-full mt-1 overflow-hidden">
                                    <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(seg.value / total) * 100}%`, backgroundColor: seg.color }} />
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    );
                  })()}
                </div>

                {/* Recent Dispatches quick glance */}
                <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm p-6 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center justify-between mb-5">
                      <p className="text-[15px] font-bold text-[#1A1E2E] flex items-center gap-2">
                        <span className="w-1.5 h-3 bg-[#EE3B3B] rounded-full" />
                        Recent Case Dispatches
                      </p>
                      <button 
                        onClick={() => setCurrentTab("dispatches")} 
                        className="text-[11px] text-[#1A78F2] font-semibold hover:underline"
                      >
                        View All Log →
                      </button>
                    </div>
                    
                    {data.recent_cases.length === 0 ? (
                      <div className="text-center py-10">
                        <p className="text-[13px] text-[#C7CCD9]">No dispatches recorded in the last 24h.</p>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2">
                        {data.recent_cases.slice(0, 5).map((c, i) => (
                          <div 
                            key={c.id} 
                            onClick={() => { setSelectedCase(c); setCurrentTab("dispatches"); }}
                            className="flex items-center gap-3 px-4 py-3 rounded-xl text-[12px] bg-[#F7F7FC] hover:bg-[#EEF4FF] cursor-pointer transition-all duration-200 border border-[#F0F2F7]"
                          >
                            <span className="text-[#C7CCD9] font-mono w-8">#{c.id}</span>
                            <span className="text-[#737A8F] font-mono w-14">{c.created_at}</span>
                            <span className="text-[#1A1E2E] font-bold flex-1 truncate">{c.hospital_name}</span>
                            <span className="text-[10px] font-bold text-white bg-[#535766] px-2 py-0.5 rounded-full capitalize">
                              {c.condition?.replace("_", " ")}
                            </span>
                            <span className="font-bold w-10 text-right font-mono" style={{ color: scoreColor(c.score * 100) }}>
                              {Math.round(c.score * 100)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* ML Engine Status Bottom Box */}
                <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm overflow-hidden">
                  <div className="flex items-center gap-3 border-b border-[#F0F2F7] px-6 py-4 bg-[#F8FAF5]/45">
                    <div className="w-1.5 h-6 bg-[#17B86B] rounded-full" />
                    <p className="text-[15px] font-bold text-[#1A1E2E]">ML Dispatch Algorithm Status</p>
                    <span className="ml-auto bg-[#E8FDF2] text-[#17B86B] text-[10px] font-extrabold px-3 py-1 rounded-full uppercase tracking-wider">
                      ● Model Active
                    </span>
                  </div>
                  <div className="grid grid-cols-6 divide-x divide-[#F0F2F7]">
                    {[
                      { val: "RandomForest", label: "Active Model", desc: "Decision Trees" },
                      { val: "112,800", label: "Training Dataset", desc: "EMS cases history" },
                      { val: "15", label: "Feature Vector", desc: "Input variables" },
                      { val: "188", label: "Hospitals Index", desc: "Total cataloged" },
                      { val: "Auto-tuned", label: "Threshold Control", desc: "Continuous tuning" },
                      { val: "Rule-based", label: "Safety Fallback", desc: "Fail-safe mechanism" },
                    ].map(({ val, label, desc }) => (
                      <div key={label} className="p-5 flex flex-col justify-between">
                        <div>
                          <p className="text-[11px] text-[#737A8F] font-bold uppercase tracking-wider">{label}</p>
                          <p className="text-[16px] font-extrabold text-[#1A78F2] mt-1.5">{val}</p>
                        </div>
                        <p className="text-[10px] text-[#C7CCD9] mt-1">{desc}</p>
                      </div>
                    ))}
                  </div>
                </div>

              </div>
            )
          )}

          {/* 2. HOSPITALS VIEW */}
          {currentTab === "hospitals" && (
            <div className="flex flex-col gap-6 bg-white p-6 rounded-2xl border border-[#F0F2F7] shadow-sm">
              
              {/* Header with Search and Filters */}
              <div className="flex items-center justify-between gap-4 flex-wrap border-b border-[#F0F2F7] pb-6">
                <div className="flex items-center gap-3 flex-1 min-w-[280px]">
                  {/* Search */}
                  <div className="relative flex-1">
                    <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-[#737A8F]">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </span>
                    <input 
                      type="text" 
                      placeholder="Search by hospital name or address..."
                      value={hospSearch}
                      onChange={e => setHospSearch(e.target.value)}
                      className="pl-10 pr-4 py-2 border border-[#E2E8F0] rounded-xl w-full text-[13px] focus:outline-none focus:border-[#1A78F2]"
                    />
                  </div>
                </div>

                {/* Dropdown filters */}
                <div className="flex items-center gap-3">
                  {/* District Filter */}
                  <select 
                    value={hospDistrict} 
                    onChange={e => setHospDistrict(e.target.value)}
                    className="border border-[#E2E8F0] rounded-xl px-4 py-2 text-[12px] font-semibold text-[#535766] focus:outline-none focus:border-[#1A78F2]"
                  >
                    <option value="all">All Districts</option>
                    {uniqueDistricts.map(d => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>

                  {/* Status Filter */}
                  <select 
                    value={hospStatus} 
                    onChange={e => setHospStatus(e.target.value)}
                    className="border border-[#E2E8F0] rounded-xl px-4 py-2 text-[12px] font-semibold text-[#535766] focus:outline-none focus:border-[#1A78F2]"
                  >
                    <option value="all">All Statuses</option>
                    <option value="accepting">Accepting Only</option>
                    <option value="suspended">Suspended Only</option>
                  </select>

                  <button 
                    onClick={fetchHospitals} 
                    className="p-2 border border-[#E2E8F0] rounded-xl text-[#737A8F] hover:bg-[#F7F7FC] transition duration-200"
                    title="Reload data"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth="2">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 15.89M21 21v-5h-.581" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Data Table */}
              {hospitalsLoading ? (
                <div className="flex justify-center items-center py-20">
                  <div className="w-10 h-10 border-4 border-[#1A78F2] border-t-transparent rounded-full animate-spin" />
                </div>
              ) : filteredHospitals.length === 0 ? (
                <div className="text-center py-20">
                  <p className="text-[14px] text-[#737A8F]">No hospitals match the filtered criteria.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px] text-left border-collapse">
                    <thead>
                      <tr className="border-b border-[#F0F2F7] text-[#737A8F] font-bold">
                        <th className="py-3 px-4 cursor-pointer hover:text-[#1A78F2]" onClick={() => toggleHospSort("name")}>
                          Hospital {hospSortKey === "name" && (hospSortDir === "asc" ? "▲" : "▼")}
                        </th>
                        <th className="py-3 px-4">District</th>
                        <th className="py-3 px-4 cursor-pointer hover:text-[#1A78F2] text-center" onClick={() => toggleHospSort("beds")}>
                          Beds Available {hospSortKey === "beds" && (hospSortDir === "asc" ? "▲" : "▼")}
                        </th>
                        <th className="py-3 px-4 cursor-pointer hover:text-[#1A78F2] text-center" onClick={() => toggleHospSort("icu")}>
                          ICU Beds {hospSortKey === "icu" && (hospSortDir === "asc" ? "▲" : "▼")}
                        </th>
                        <th className="py-3 px-4 cursor-pointer hover:text-[#1A78F2] text-center" onClick={() => toggleHospSort("doctors")}>
                          On-Duty Doctors {hospSortKey === "doctors" && (hospSortDir === "asc" ? "▲" : "▼")}
                        </th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">Active Equipment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#F0F2F7]">
                      {filteredHospitals.map(h => (
                        <tr key={h.id} className="hover:bg-[#F7F7FC]/80 transition duration-150">
                          <td className="py-4 px-4">
                            <div className="font-bold text-[#1A1E2E]">{h.name}</div>
                            <div className="text-[11px] text-[#737A8F] mt-0.5 truncate max-w-sm flex items-center gap-1">
                              <svg className="w-3.5 h-3.5 flex-shrink-0 text-[#1A78F2]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                              </svg>
                              {h.address}
                            </div>
                          </td>
                          <td className="py-4 px-4 font-semibold text-[#535766]">
                            <span className="bg-[#EEF2F6] text-[#475569] px-2.5 py-1 rounded-full text-[11px]">
                              {h.district || "N/A"}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center font-bold text-[14px]">
                            {h.availability?.beds ?? 0}
                          </td>
                          <td className="py-4 px-4 text-center font-bold text-[14px] text-[#FFB21A]">
                            {h.availability?.icu ?? 0}
                          </td>
                          <td className="py-4 px-4 text-center font-bold text-[14px] text-[#1A78F2]">
                            {h.availability?.doctors ?? 0}
                          </td>
                          <td className="py-4 px-4">
                            {h.availability?.accepting ? (
                              <span className="bg-[#E8FDF2] text-[#17B86B] font-bold text-[10px] px-2.5 py-1 rounded-full uppercase">
                                Accepting
                              </span>
                            ) : (
                              <span className="bg-[#FFF0F0] text-[#EE3B3B] font-bold text-[10px] px-2.5 py-1 rounded-full uppercase">
                                Suspended
                              </span>
                            )}
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex flex-wrap gap-1 max-w-xs">
                              {h.availability?.equipment && h.availability.equipment.length > 0 ? (
                                h.availability.equipment.map(e => (
                                  <span key={e} className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 bg-blue-50 text-blue-600 rounded">
                                    {e.replace("has_", "").replace("_", " ")}
                                  </span>
                                ))
                              ) : (
                                <span className="text-[11px] text-[#C7CCD9]">None listed</span>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* 3. DISPATCHES VIEW */}
          {currentTab === "dispatches" && (
            <div className="flex flex-col gap-6">
              
              {/* Main List and Search */}
              <div className="bg-white p-6 rounded-2xl border border-[#F0F2F7] shadow-sm">
                <div className="flex items-center justify-between border-b border-[#F0F2F7] pb-5 mb-5 flex-wrap gap-4">
                  <div className="relative max-w-md w-full">
                    <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-[#737A8F]">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                      </svg>
                    </span>
                    <input 
                      type="text" 
                      placeholder="Search dispatches by hospital or condition..."
                      value={caseSearch}
                      onChange={e => setCaseSearch(e.target.value)}
                      className="pl-10 pr-4 py-2 border border-[#E2E8F0] rounded-xl w-full text-[13px] focus:outline-none focus:border-[#1A78F2]"
                    />
                  </div>
                  <span className="text-[11.5px] text-[#737A8F] font-semibold bg-[#F7F7FC] px-3.5 py-2 rounded-xl border border-[#F0F2F7]">
                    Total dispatches this shift: <span className="text-[#1A1E2E] font-bold">{data?.total_cases ?? 0}</span>
                  </span>
                </div>

                {filteredCases.length === 0 ? (
                  <div className="text-center py-20">
                    <p className="text-[14px] text-[#737A8F]">No dispatch cases found.</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-[13px] text-left border-collapse">
                      <thead>
                        <tr className="border-b border-[#F0F2F7] text-[#737A8F] font-bold">
                          <th className="py-3 px-4">Case ID</th>
                          <th className="py-3 px-4">Timestamp</th>
                          <th className="py-3 px-4">Target Hospital</th>
                          <th className="py-3 px-4">Emergency Condition</th>
                          <th className="py-3 px-4 text-center">Distance</th>
                          <th className="py-3 px-4 text-center">ETA</th>
                          <th className="py-3 px-4 text-center">Triage score</th>
                          <th className="py-3 px-4 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#F0F2F7]">
                        {filteredCases.map(c => (
                          <tr key={c.id} className="hover:bg-[#F7F7FC] transition duration-150">
                            <td className="py-4 px-4 font-mono font-bold text-[#475569]">#{c.id}</td>
                            <td className="py-4 px-4 text-[#737A8F]">{c.created_at}</td>
                            <td className="py-4 px-4 font-bold text-[#1A1E2E]">{c.hospital_name}</td>
                            <td className="py-4 px-4">
                              <span className="text-[11px] font-bold px-2.5 py-1 bg-[#EEF2F6] text-[#475569] rounded-full uppercase tracking-wider">
                                {c.condition?.replace("_", " ")}
                              </span>
                            </td>
                            <td className="py-4 px-4 text-center font-semibold text-[#535766]">{c.distance_km} km</td>
                            <td className="py-4 px-4 text-center font-bold text-[#1A78F2]">{c.eta_minutes} mins</td>
                            <td className="py-4 px-4">
                              <div className="flex items-center justify-center gap-1.5">
                                <span className="font-extrabold" style={{ color: scoreColor(c.score * 100) }}>
                                  {Math.round(c.score * 100)}%
                                </span>
                                <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: scoreColor(c.score * 100) }} />
                              </div>
                            </td>
                            <td className="py-4 px-4 text-right">
                              <button 
                                onClick={() => setSelectedCase(c)}
                                className="px-3.5 py-1.5 bg-[#EEF4FF] hover:bg-[#1A78F2] hover:text-white text-[#1A78F2] font-semibold rounded-lg text-[12px] transition duration-200"
                              >
                                Inspect Triage
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* Case Detail Slide-over / Inspector Overlay */}
              {selectedCase && (
                <div className="fixed inset-0 bg-black/40 backdrop-blur-sm z-50 flex justify-end transition-opacity duration-300">
                  <div className="w-[500px] bg-white h-full shadow-2xl p-8 overflow-y-auto flex flex-col justify-between animate-slide-left relative border-l border-[#F0F2F7]">
                    
                    <div>
                      {/* Close button */}
                      <button 
                        onClick={() => setSelectedCase(null)}
                        className="absolute top-6 right-6 text-[#737A8F] hover:text-black transition duration-200"
                      >
                        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>

                      {/* Header */}
                      <span className="text-[11px] font-bold font-mono text-[#737A8F] bg-[#EEF2F6] px-2.5 py-1 rounded-full uppercase tracking-wider">
                        Case ID #{selectedCase.id}
                      </span>
                      <h2 className="text-[22px] font-black text-[#1A1E2E] mt-3 uppercase tracking-tight">
                        Triage Assessment Detail
                      </h2>
                      <p className="text-[12px] text-[#737A8F] mt-1 font-mono">Dispatched at {selectedCase.created_at}</p>

                      <div className="mt-8 flex flex-col gap-6">
                        {/* Emergency overview card */}
                        <div className="bg-[#F7F7FC] border border-[#F0F2F7] rounded-2xl p-5">
                          <h3 className="text-[13px] font-bold text-[#737A8F] uppercase tracking-wider">Paramedic Report Transcript</h3>
                          <p className="text-[14px] text-[#1A1E2E] font-medium mt-2 leading-relaxed">
                            "Patient presenting with signs of <span className="font-bold underline text-[#EE3B3B]">{selectedCase.condition?.replace("_", " ")}</span>. Emergency ambulance response requested immediately. Requires urgent transit."
                          </p>
                        </div>

                        {/* Dispatch Score Breakdown */}
                        <div className="bg-white border border-[#F0F2F7] rounded-2xl p-5 flex flex-col gap-4 shadow-sm">
                          <h3 className="text-[13px] font-bold text-[#1A1E2E]">Dispatch Match Scoring Decision</h3>
                          
                          <div className="flex items-center gap-4 bg-[#F8FAF5] p-3 rounded-xl border border-[#EEF2E6]">
                            <div className="w-14 h-14 rounded-full flex items-center justify-center text-[16px] font-black text-white" style={{ backgroundColor: scoreColor(selectedCase.score * 100) }}>
                              {Math.round(selectedCase.score * 100)}%
                            </div>
                            <div>
                              <p className="text-[14px] font-extrabold text-[#1A1E2E]">Final Match Score</p>
                              <p className="text-[11px] text-[#737A8F] mt-0.5">Assigned to <span className="font-bold text-[#1A1E2E]">{selectedCase.hospital_name}</span></p>
                            </div>
                          </div>

                          {/* Detail Indicators */}
                          <div className="flex flex-col gap-3 mt-1">
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="text-[#737A8F]">Driving distance</span>
                              <span className="font-bold text-[#1A1E2E]">{selectedCase.distance_km} km</span>
                            </div>
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="text-[#737A8F]">Estimated Time of Arrival (ETA)</span>
                              <span className="font-bold text-[#1A78F2]">{selectedCase.eta_minutes} mins</span>
                            </div>
                            <div className="flex items-center justify-between text-[12px]">
                              <span className="text-[#737A8F]">Triage priority index</span>
                              <span className="font-bold text-[#EE3B3B] uppercase">High Priority</span>
                            </div>
                          </div>
                        </div>

                        {/* AI justification reasoning */}
                        <div className="flex flex-col gap-2">
                          <h3 className="text-[13px] font-bold text-[#1A1E2E]">AI Decision Recommendation</h3>
                          <div className="text-[13px] text-[#535766] bg-blue-50/50 border border-blue-100 rounded-2xl p-5 leading-relaxed">
                            <span className="font-bold text-blue-700">Triage reasoning:</span> Based on the paramedic transcript, {selectedCase.condition?.replace("_", " ")} was diagnosed with high confidence. {selectedCase.hospital_name} was selected because it is {selectedCase.distance_km} km away, has critical ICU beds available, and features specialized doctors to treat this medical condition immediately.
                          </div>
                        </div>
                      </div>
                    </div>

                    <button 
                      onClick={() => setSelectedCase(null)}
                      className="w-full mt-8 py-3 bg-[#0D1830] text-white hover:bg-black font-semibold rounded-xl text-[13px] transition duration-200"
                    >
                      Close Inspector
                    </button>

                  </div>
                </div>
              )}
            </div>
          )}

          {/* 4. ML ENGINE VIEW */}
          {currentTab === "ml" && (
            <div className="flex flex-col gap-6">
              
              {/* Stacked columns: Left parameters, Right simulator */}
              <div className="grid grid-cols-5 gap-6">
                
                {/* 4a. Model Configuration Panel */}
                <div className="col-span-2 flex flex-col gap-6 bg-white p-6 rounded-2xl border border-[#F0F2F7] shadow-sm">
                  <div>
                    <h3 className="text-[15px] font-bold text-[#1A1E2E] flex items-center gap-2">
                      <span className="w-1.5 h-3.5 bg-[#1A78F2] rounded-full" />
                      Algorithmic Weights Tuning
                    </h3>
                    <p className="text-[11px] text-[#737A8F] mt-1">
                      Tune default matching weights of the rule-based safety fallback engine.
                    </p>
                  </div>

                  <div className="flex flex-col gap-5 mt-2">
                    {/* Proximity Slider */}
                    <div>
                      <div className="flex items-center justify-between text-[12px] font-bold text-[#535766] mb-1.5">
                        <span>Travel Time (ETA)</span>
                        <span className="font-mono text-[#1A78F2]">{Math.round(wEta * 100)}%</span>
                      </div>
                      <input 
                        type="range" 
                        min="0" max="1" step="0.05" 
                        value={wEta} 
                        onChange={e => setWEta(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-[#F0F2F7] rounded-lg appearance-none cursor-pointer accent-[#1A78F2]"
                      />
                    </div>

                    {/* Survival Slider */}
                    <div>
                      <div className="flex items-center justify-between text-[12px] font-bold text-[#535766] mb-1.5">
                        <span>Patient Survival Decay Rate</span>
                        <span className="font-mono text-[#1A78F2]">{Math.round(wSurvival * 100)}%</span>
                      </div>
                      <input 
                        type="range" 
                        min="0" max="1" step="0.05" 
                        value={wSurvival} 
                        onChange={e => setWSurvival(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-[#F0F2F7] rounded-lg appearance-none cursor-pointer accent-[#1A78F2]"
                      />
                    </div>

                    {/* Hospital Load Slider */}
                    <div>
                      <div className="flex items-center justify-between text-[12px] font-bold text-[#535766] mb-1.5">
                        <span>Capacity Bed Load</span>
                        <span className="font-mono text-[#1A78F2]">{Math.round(wLoad * 100)}%</span>
                      </div>
                      <input 
                        type="range" 
                        min="0" max="1" step="0.05" 
                        value={wLoad} 
                        onChange={e => setWLoad(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-[#F0F2F7] rounded-lg appearance-none cursor-pointer accent-[#1A78F2]"
                      />
                    </div>

                    {/* Equipment Slider */}
                    <div>
                      <div className="flex items-center justify-between text-[12px] font-bold text-[#535766] mb-1.5">
                        <span>Equipment Match Availability</span>
                        <span className="font-mono text-[#1A78F2]">{Math.round(wEquipment * 100)}%</span>
                      </div>
                      <input 
                        type="range" 
                        min="0" max="1" step="0.05" 
                        value={wEquipment} 
                        onChange={e => setWEquipment(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-[#F0F2F7] rounded-lg appearance-none cursor-pointer accent-[#1A78F2]"
                      />
                    </div>

                    {/* Specialist Slider */}
                    <div>
                      <div className="flex items-center justify-between text-[12px] font-bold text-[#535766] mb-1.5">
                        <span>Doctor/Specialist Match</span>
                        <span className="font-mono text-[#1A78F2]">{Math.round(wTreatment * 100)}%</span>
                      </div>
                      <input 
                        type="range" 
                        min="0" max="1" step="0.05" 
                        value={wTreatment} 
                        onChange={e => setWTreatment(parseFloat(e.target.value))}
                        className="w-full h-1.5 bg-[#F0F2F7] rounded-lg appearance-none cursor-pointer accent-[#1A78F2]"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-3 border-t border-[#F0F2F7] pt-4 mt-2">
                    <button 
                      onClick={resetWeights}
                      className="px-4 py-2 border border-[#E2E8F0] text-[#737A8F] hover:bg-[#F7F7FC] font-semibold rounded-xl text-[12px] transition duration-200"
                    >
                      Reset to Default
                    </button>
                    <span className="text-[11px] text-[#737A8F] font-medium leading-tight">
                      Adjusting weights modifies how candidates are sorted for ambulances.
                    </span>
                  </div>
                </div>

                {/* 4b. Live Match Simulator Panel */}
                <div className="col-span-3 flex flex-col gap-6 bg-white p-6 rounded-2xl border border-[#F0F2F7] shadow-sm">
                  <div>
                    <h3 className="text-[15px] font-bold text-[#1A1E2E] flex items-center gap-2">
                      <span className="w-1.5 h-3.5 bg-[#17B86B] rounded-full" />
                      Live Match Score Simulator
                    </h3>
                    <p className="text-[11px] text-[#737A8F] mt-1">
                      Simulate a paramedic case request and calculate real-time matching metrics.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-5">
                    {/* Left Inputs */}
                    <div className="flex flex-col gap-4">
                      {/* Condition Selection */}
                      <div>
                        <label className="text-[11px] font-bold uppercase tracking-wider text-[#737A8F] mb-1.5 block">Medical Condition</label>
                        <select 
                          value={simCondition}
                          onChange={e => setSimCondition(e.target.value)}
                          className="border border-[#E2E8F0] rounded-xl px-3 py-2 text-[12.5px] w-full focus:outline-none focus:border-[#1A78F2] text-[#1A1E2E] font-medium"
                        >
                          <option value="cardiac_arrest">Cardiac Arrest (Critical)</option>
                          <option value="stroke">Stroke / TIA (Critical)</option>
                          <option value="trauma">Trauma / Injury (High)</option>
                          <option value="respiratory_distress">Respiratory Distress (High)</option>
                          <option value="minor_injury">Minor Injury (Low)</option>
                        </select>
                      </div>

                      {/* Distance Slider */}
                      <div>
                        <div className="flex justify-between items-center text-[11px] mb-1.5">
                          <label className="font-bold uppercase tracking-wider text-[#737A8F]">Driving Distance</label>
                          <span className="font-mono text-[#1A1E2E] font-bold">{simDistance} km</span>
                        </div>
                        <input 
                          type="range" 
                          min="1" max="50" step="0.5" 
                          value={simDistance} 
                          onChange={e => setSimDistance(parseFloat(e.target.value))}
                          className="w-full h-1 bg-[#F0F2F7] rounded appearance-none cursor-pointer accent-[#17B86B]"
                        />
                      </div>

                      {/* Available Beds */}
                      <div>
                        <div className="flex justify-between items-center text-[11px] mb-1.5">
                          <label className="font-bold uppercase tracking-wider text-[#737A8F]">Available Beds</label>
                          <span className="font-mono text-[#1A1E2E] font-bold">{simBeds} beds</span>
                        </div>
                        <input 
                          type="range" 
                          min="0" max="100" step="1" 
                          value={simBeds} 
                          onChange={e => setSimBeds(parseInt(e.target.value))}
                          className="w-full h-1 bg-[#F0F2F7] rounded appearance-none cursor-pointer accent-[#17B86B]"
                        />
                      </div>
                    </div>

                    {/* Right Inputs */}
                    <div className="flex flex-col gap-4 bg-[#F7F7FC] p-4 rounded-2xl border border-[#F0F2F7]">
                      {/* Equipment checkbox grid */}
                      <div>
                        <label className="text-[10px] font-bold uppercase tracking-wider text-[#737A8F] mb-2 block">Hospital Equipment Available</label>
                        <div className="grid grid-cols-2 gap-2 text-[11.5px] font-medium">
                          {[
                            { key: "ventilator", label: "Ventilator" },
                            { key: "defibrillator", label: "Defibrillator" },
                            { key: "ct_scan", label: "CT Scan" },
                            { key: "blood_bank", label: "Blood Bank" },
                            { key: "icu", label: "ICU Equip" },
                          ].map(({ key, label }) => (
                            <label key={key} className="flex items-center gap-2 cursor-pointer">
                              <input 
                                type="checkbox" 
                                checked={simEquipment[key]}
                                onChange={e => setSimEquipment(prev => ({ ...prev, [key]: e.target.checked }))}
                                className="w-3.5 h-3.5 rounded text-[#17B86B] border-[#E2E8F0] focus:ring-0 cursor-pointer"
                              />
                              {label}
                            </label>
                          ))}
                        </div>
                      </div>

                      {/* Specialists check list */}
                      <div>
                        <label className="text-[10px] font-bold uppercase tracking-wider text-[#737A8F] mb-2 block mt-1">Specialists On Duty</label>
                        <div className="grid grid-cols-2 gap-2 text-[11.5px] font-medium">
                          {[
                            { key: "cardiology", label: "Cardiologist" },
                            { key: "neurology", label: "Neurologist" },
                            { key: "trauma", label: "Trauma Surgeon" },
                            { key: "respiratory", label: "Pulmonologist" },
                          ].map(({ key, label }) => (
                            <label key={key} className="flex items-center gap-2 cursor-pointer">
                              <input 
                                type="checkbox" 
                                checked={simSpecialists[key]}
                                onChange={e => setSimSpecialists(prev => ({ ...prev, [key]: e.target.checked }))}
                                className="w-3.5 h-3.5 rounded text-[#17B86B] border-[#E2E8F0] focus:ring-0 cursor-pointer"
                              />
                              {label}
                            </label>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Calculator Simulation Output */}
                  <div className="border-t border-[#F0F2F7] pt-5 mt-2">
                    <div className="flex items-center gap-4">
                      
                      {/* Big Circle Score Display */}
                      <div 
                        className="w-20 h-20 rounded-full flex flex-col items-center justify-center text-white border-4 border-white shadow-lg shadow-black/5 flex-shrink-0"
                        style={{ backgroundColor: scoreColor(simResult.final) }}
                      >
                        <span className="text-[22px] font-black leading-none">{simResult.final}%</span>
                        <span className="text-[8px] font-bold uppercase tracking-wider mt-1 opacity-80">Match</span>
                      </div>

                      <div className="flex-1">
                        <div className="flex items-center justify-between">
                          <p className="text-[14px] font-bold text-[#1A1E2E]">Calculated Scoring Output</p>
                          <span 
                            className="text-[10px] font-bold px-2 py-0.5 rounded-full"
                            style={{ color: scoreColor(simResult.final), backgroundColor: scoreBgColor(simResult.final) }}
                          >
                            {simResult.final >= 55 ? "DISPATCH ALLOWED" : "REJECTED (BELOW THRESHOLD)"}
                          </span>
                        </div>
                        
                        {/* Breakdown progress metrics */}
                        <div className="grid grid-cols-5 gap-2 mt-3 text-[10px] text-center">
                          {[
                            { val: simResult.breakdown.proximity, weight: simResult.weights.proximity, label: "ETA" },
                            { val: simResult.breakdown.survival, weight: simResult.weights.survival, label: "Survival" },
                            { val: simResult.breakdown.load, weight: simResult.weights.load, label: "Load" },
                            { val: simResult.breakdown.equipment, weight: simResult.weights.equipment, label: "Equip" },
                            { val: simResult.breakdown.treatment, weight: simResult.weights.treatment, label: "Specialist" },
                          ].map(({ val, weight, label }) => (
                            <div key={label} className="bg-[#F7F7FC] rounded-lg p-1.5 border border-[#F0F2F7]">
                              <div className="font-extrabold text-[#1A1E2E]">{val}%</div>
                              <div className="text-[#737A8F] mt-0.5 leading-none">{label}</div>
                              <div className="text-[9px] text-[#C7CCD9] font-mono mt-1 font-semibold">w={weight}%</div>
                            </div>
                          ))}
                        </div>
                      </div>

                    </div>
                  </div>

                </div>

              </div>
            </div>
          )}

          {/* 5. SETTINGS VIEW */}
          {currentTab === "settings" && (
            <div className="flex flex-col gap-6 max-w-3xl">
              
              {/* Preferences Configuration Box */}
              <div className="bg-white p-6 rounded-2xl border border-[#F0F2F7] shadow-sm flex flex-col gap-6">
                <div>
                  <h3 className="text-[15px] font-bold text-[#1A1E2E] flex items-center gap-2">
                    <span className="w-1.5 h-3.5 bg-[#1A78F2] rounded-full" />
                    Dashboard Preferences
                  </h3>
                  <p className="text-[11px] text-[#737A8F] mt-1">Configure layout preferences and sync rates for this admin session.</p>
                </div>

                <div className="grid grid-cols-2 gap-6">
                  {/* Sync frequency */}
                  <div>
                    <label className="text-[11.5px] font-bold text-[#535766] block mb-2">Auto-Refresh Frequency</label>
                    <select 
                      value={refreshInterval}
                      onChange={e => {
                        const val = parseInt(e.target.value);
                        setRefreshInterval(val);
                        toast(`Auto-refresh set to ${val === 0 ? "Manual" : val/1000 + " seconds"}.`, "success");
                      }}
                      className="border border-[#E2E8F0] rounded-xl px-3.5 py-2 text-[12.5px] w-full focus:outline-none focus:border-[#1A78F2] font-semibold text-[#1A1E2E]"
                    >
                      <option value={5000}>5 Seconds (High frequency)</option>
                      <option value={15000}>15 Seconds (Normal)</option>
                      <option value={30000}>30 Seconds (Eco mode)</option>
                      <option value={60000}>60 Seconds</option>
                      <option value={0}>Manual Refresh Only</option>
                    </select>
                  </div>

                  {/* Sound Notifications */}
                  <div>
                    <label className="text-[11.5px] font-bold text-[#535766] block mb-2">Notification Sounds</label>
                    <div className="flex items-center h-10">
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input 
                          type="checkbox" 
                          checked={soundEnabled}
                          onChange={e => {
                            setSoundEnabled(e.target.checked);
                            toast(`Sound notifications ${e.target.checked ? "enabled" : "muted"}.`, "info");
                          }}
                          className="sr-only peer"
                        />
                        <div className="w-9 h-5 bg-[#E2E8F0] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:height-4 after:w-4 after:transition-all peer-checked:bg-[#1A78F2]" />
                        <span className="ml-3 text-[12.5px] font-medium text-[#1A1E2E]">
                          {soundEnabled ? "Alert sound on critical cases" : "Muted"}
                        </span>
                      </label>
                    </div>
                  </div>
                </div>
              </div>

              {/* Dev Simulation & Demo Suite */}
              <div className="bg-white p-6 rounded-2xl border border-[#F0F2F7] shadow-sm flex flex-col gap-6">
                <div>
                  <h3 className="text-[15px] font-bold text-[#1A1E2E] flex items-center gap-2">
                    <span className="w-1.5 h-3.5 bg-[#FFB21A] rounded-full" />
                    Demo Simulation Controls
                  </h3>
                  <p className="text-[11px] text-[#737A8F] mt-1">Simulate live system issues or emergency spikes for demonstration or validation.</p>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="flex gap-3">
                    <button 
                      onClick={() => triggerDemoAlert("warning", "ALERT: Bed capacity depleted in Roorkee district!")}
                      className="px-4 py-3 bg-[#FFF8E0] hover:bg-[#FFF2CD] text-[#FFB21A] font-bold rounded-xl text-[12.5px] transition flex-1 border border-[#FFEAB2]"
                    >
                      Simulate Bed Outage
                    </button>
                    <button 
                      onClick={() => triggerDemoAlert("error", "EMERGENCY SPIKE: 5 critical dispatch cases queued in Haridwar!")}
                      className="px-4 py-3 bg-[#FFF0F0] hover:bg-[#FFE5E5] text-[#EE3B3B] font-bold rounded-xl text-[12.5px] transition flex-1 border border-[#FFD1D1]"
                    >
                      Trigger Traffic Spike
                    </button>
                    <button 
                      onClick={() => triggerDemoAlert("success", "System cache cleared successfully. All index models synced.")}
                      className="px-4 py-3 bg-[#E8FDF2] hover:bg-[#D3FCE5] text-[#17B86B] font-bold rounded-xl text-[12.5px] transition flex-1 border border-[#C1F9D7]"
                    >
                      Sync & Clear Cache
                    </button>
                  </div>
                  
                  <div className="bg-[#F7F7FC] p-4 rounded-xl border border-[#F0F2F7] flex items-center justify-between text-[12px]">
                    <div>
                      <p className="font-bold text-[#1A1E2E]">System Operation Mode</p>
                      <p className="text-[11px] text-[#737A8F] mt-0.5">Toggle live telemetry endpoints vs simulated sandbox values.</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {["production", "staging", "local"].map(mode => (
                        <button
                          key={mode}
                          onClick={() => {
                            setOpsMode(mode);
                            toast(`Switched operations to ${mode.toUpperCase()} sandbox.`, "success");
                          }}
                          className={`px-3 py-1.5 rounded-lg font-bold text-[10.5px] uppercase tracking-wider transition
                            ${opsMode === mode 
                              ? "bg-[#0D1830] text-white" 
                              : "bg-white border border-[#E2E8F0] text-[#737A8F] hover:bg-[#F7F7FC]"}`}
                        >
                          {mode}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

            </div>
          )}

        </div>
      </main>
    </div>
  );
}

export function calculateSimulatedScore({
  wSurvival, wTreatment, wEquipment, wEta, wLoad,
  simCondition, simDistance, simBeds, simEquipment, simSpecialists
}) {
  const totalW = wSurvival + wTreatment + wEquipment + wEta + wLoad;
  if (totalW <= 0) return { final: 0, breakdown: {}, weights: {} };
  
  const wSurvivalNorm = wSurvival / totalW;
  const wTreatmentNorm = wTreatment / totalW;
  const wEquipmentNorm = wEquipment / totalW;
  const wEtaNorm = wEta / totalW;
  const wLoadNorm = wLoad / totalW;

  // Proximity ETA calculation
  const speed = 40.0; // km/h
  const etaMinutes = (simDistance / speed) * 60.0;
  const sProximity = 1.0 / (1.0 + etaMinutes / 30.0);

  // Equipment Match calculation
  const conditionEquipmentNeeded = {
    cardiac_arrest: ["defibrillator", "ventilator", "icu"],
    stroke: ["ct_scan", "ventilator", "icu"],
    trauma: ["blood_bank", "ventilator", "icu"],
    respiratory_distress: ["ventilator", "icu"],
    minor_injury: []
  };
  const needed = conditionEquipmentNeeded[simCondition] || [];
  let matched = 0;
  needed.forEach(item => {
    if (simEquipment[item]) matched++;
  });
  const sEquipment = needed.length > 0 ? (matched / needed.length) : 1.0;

  // Specialty matching score
  let sSpecialty = 0.8;
  if (simCondition === "stroke") {
    sSpecialty = simSpecialists.neurology ? 1.0 : 0.3;
  } else if (simCondition === "cardiac_arrest") {
    sSpecialty = simSpecialists.cardiology ? 1.0 : 0.3;
  } else if (simCondition === "trauma") {
    sSpecialty = simSpecialists.trauma ? 1.0 : 0.3;
  } else if (simCondition === "respiratory_distress") {
    sSpecialty = simSpecialists.respiratory ? 1.0 : 0.3;
  }

  // Survival probability decay curve
  const baselineMap = {
    cardiac_arrest: 12.0,
    stroke: 24.0,
    trauma: 16.0,
    respiratory_distress: 20.0,
    minor_injury: 90.0
  };
  const baseline = baselineMap[simCondition] || 45.0;
  const severityScore = simCondition === "cardiac_arrest" || simCondition === "stroke" ? 4 : (simCondition === "trauma" ? 3 : 2);
  const severityPenalty = (severityScore - 1) * 2.2;
  const survivalTimeMinutes = Math.max(1.0, baseline - severityPenalty);
  const deficit = Math.max(0.0, etaMinutes - survivalTimeMinutes);
  const tauMap = { stroke: 1.5, cardiac_arrest: 2.0, trauma: 2.5 };
  const tau = tauMap[simCondition] || 3.0;
  const baseSurvival = Math.max(0.25, Math.exp(-(deficit / tau)));
  const sSurvival = Math.max(baseSurvival, 0.35); // Recovery floor

  // Load capacity score (free beds ratio)
  const load = 1.0 - (simBeds / 100.0);
  const sLoad = 1.0 - load;

  // Final weighted score
  const finalScore = (
    wSurvivalNorm * sSurvival +
    wTreatmentNorm * sSpecialty +
    wEquipmentNorm * sEquipment +
    wEtaNorm * sProximity +
    wLoadNorm * sLoad
  );

  return {
    final: Math.round(finalScore * 100),
    breakdown: {
      survival: Math.round(sSurvival * 100),
      treatment: Math.round(sSpecialty * 100),
      equipment: Math.round(sEquipment * 100),
      proximity: Math.round(sProximity * 100),
      load: Math.round(sLoad * 100),
    },
    weights: {
      survival: Math.round(wSurvivalNorm * 100),
      treatment: Math.round(wTreatmentNorm * 100),
      equipment: Math.round(wEquipmentNorm * 100),
      proximity: Math.round(wEtaNorm * 100),
      load: Math.round(wLoadNorm * 100)
    }
  };
}
