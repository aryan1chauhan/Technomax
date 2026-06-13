import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import api from "../api/axios";
import CaseTimeline from "../components/CaseTimeline";
import RouteFallback from "../components/RouteFallback";

const MapWidget = lazy(() => import("../components/MapWidget"));

export default function HospitalTrack() {
  const { case_id } = useParams();
  const navigate = useNavigate();
  const wsRef = useRef(null);

  const [caseData, setCaseData] = useState(null);
  const [ambulancePos, setAmbulancePos] = useState(null);
  const [eta, setEta] = useState(null);
  const [arrived, setArrived] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isReady, setIsReady] = useState(false);
  const [hospitalInfo, setHospitalInfo] = useState({ name: "Hospital", id: "", beds: "—" });

  useEffect(() => {
    // Decode JWT to get hospital info for the sidebar
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
  }, []);

  useEffect(() => {
    const fetchCase = async () => {
      try {
        const res = await api.get("/api/cases/hospital");
        const cases = Array.isArray(res.data) ? res.data : res.data.items || [];
        const found = cases.find((entry) => String(entry.id) === String(case_id));
        if (!found) {
          setError("Case not found or not assigned to your hospital.");
          setLoading(false);
          return;
        }
        setCaseData(found);
        setEta(found.eta_minutes);
      } catch (err) {
        setError("Failed to load case data.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchCase();
  }, [case_id]);

  useEffect(() => {
    if (!case_id) return undefined;
    let reconnectTimer;

    const connect = () => {
      const token = localStorage.getItem("token");
      const apiUrl = import.meta.env.VITE_API_URL || "";
      const wsBase = apiUrl ? apiUrl.replace(/^http/, "ws") : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
      const ws = new WebSocket(`${wsBase}/ws/hospital/${case_id}?token=${token}`);
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.lat && msg.lng) setAmbulancePos([msg.lat, msg.lng]);
          if (msg.eta_minutes !== undefined) {
            setEta(msg.eta_minutes);
            if (msg.eta_minutes === 0) setArrived(true);
          }
        } catch {
          // Ignore malformed payloads from the live tracker.
        }
      };
      ws.onerror = (e) => console.error("WS error", e);
      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 2000);
      };
      wsRef.current = ws;
    };

    connect();
    return () => {
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
      }
    };
  }, [case_id]);

  const handleMarkReady = async () => {
    if (!caseData?.assigned_hospital_id) return;
    try {
      const beds = typeof caseData.available_beds === "number" ? caseData.available_beds : typeof caseData.beds === "number" ? caseData.beds : 0;
      const icu = typeof caseData.icu_beds === "number" ? caseData.icu_beds : typeof caseData.icu === "number" ? caseData.icu : 0;
      const doctors = typeof caseData.doctors === "number" ? caseData.doctors : 0;
      const equipment = Array.isArray(caseData.equipment_needed) ? caseData.equipment_needed : [];

      await api.put(`/api/hospitals/${caseData.assigned_hospital_id}/availability`, {
        beds,
        icu,
        doctors,
        equipment,
        accepting: true,
      });
      setIsReady(true);
    } catch (err) {
      console.error("Failed to mark ready:", err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    navigate("/login");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#F7F7FC] font-['Inter',sans-serif]">
        <div className="flex flex-col items-center gap-4">
          <span className="w-10 h-10 rounded-full border-4 border-t-[#1A78F2] border-r-transparent border-b-transparent border-l-transparent animate-spin" />
          <p className="text-[14px] font-semibold text-[#737A8F] uppercase tracking-wider">Loading Case Telemetry...</p>
        </div>
      </div>
    );
  }

  if (error || !caseData) {
    return (
      <div className="flex flex-col items-center justify-center h-screen bg-[#F7F7FC] font-['Inter',sans-serif] p-6 text-center">
        <div className="bg-white border border-[#F0F2F7] rounded-2xl shadow-sm p-8 max-w-md w-full">
          <span className="text-[40px]">⚠</span>
          <h2 className="text-[18px] font-bold text-[#1A1E2E] mt-3">Tracking Error</h2>
          <p className="text-[14px] text-[#737A8F] mt-2 mb-6">{error || "Case tracking is unavailable."}</p>
          <button
            onClick={() => navigate("/hospital/dashboard")}
            className="w-full bg-[#1A78F2] hover:bg-[#1560c4] text-white text-[13px] font-bold py-3 rounded-xl shadow-sm transition"
          >
            ← Return to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const hospLat = caseData.hospital_lat ?? caseData.assigned_hospital_lat ?? 30.3165;
  const hospLng = caseData.hospital_lng ?? caseData.assigned_hospital_lng ?? 78.0322;
  const hospPos = [hospLat, hospLng];
  const ambPos = ambulancePos ?? (caseData.ambulance_lat && caseData.ambulance_lng ? [caseData.ambulance_lat, caseData.ambulance_lng] : null);

  const scorePercent = Math.round((caseData.final_score || 0) * 100);
  const scoreColor = (v) => {
    const pct = Math.round((v || 0) * 100);
    return pct > 70 ? "#17B86B" : pct > 50 ? "#FFB21A" : "#EE3B3B";
  };
  const scoreBg = (v) => {
    const pct = Math.round((v || 0) * 100);
    return pct > 70 ? "#E8FDF2" : pct > 50 ? "#FFF8E0" : "#FFEDED";
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
                ${i === 1 ? "bg-[#172954] text-white font-semibold border-l-[3px] border-[#1A78F2]" : "text-[#737A8F] hover:text-white"}`}
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
            onClick={handleLogout}
            className="mt-3 text-[12px] text-[#737A8F] hover:text-white transition"
          >
            Sign out →
          </button>
        </div>
      </aside>

      {/* ── Main Workspace ── */}
      <main className="flex-1 flex flex-col overflow-hidden">
        
        {/* Top Header Bar */}
        <div className="bg-white border-b border-[#F0F2F7] h-16 flex items-center justify-between px-8 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate("/hospital/dashboard")}
              className="text-[#737A8F] hover:text-[#1A1E2E] transition flex items-center gap-1 text-[13.5px] font-medium"
            >
              ← Back to Dashboard
            </button>
            <span className="text-[#C7CCD9]">|</span>
            <h1 className="text-[18px] font-bold text-[#1A1E2E]">Ambulance Live Tracking</h1>
          </div>
          <div className="flex items-center gap-3">
            <span className={`flex items-center gap-2 text-[11px] font-extrabold px-3.5 py-1.5 rounded-full uppercase tracking-wider ${
              arrived ? "bg-[#E8FDF2] text-[#17B86B] border border-[#BFF6DC]" : "bg-[#FFEDED] text-[#EE3B3B] border border-[#FFD5D5]"
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${arrived ? "bg-[#17B86B]" : "bg-[#EE3B3B] animate-pulse"}`} />
              {arrived ? "Arrived" : "Incoming Ambulance"}
            </span>
          </div>
        </div>

        {/* Scrollable Content Workspace */}
        <div className="flex-1 overflow-y-auto p-8 bg-[#F7F7FC]">
          <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
            
            {/* Left Column (7/12 width on desktop) */}
            <div className="lg:col-span-7 flex flex-col gap-6">
              
              {/* Case Details Card */}
              <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm p-6">
                <div className="flex items-center justify-between border-b border-[#F0F2F7] pb-4 mb-5">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] font-mono font-bold text-[#737A8F] bg-[#F0F2F7] px-2.5 py-1 rounded-lg">
                      CASE #{caseData.id}
                    </span>
                    <h2 className="text-[15px] font-extrabold text-[#1A1E2E]">Triage & Route Diagnostics</h2>
                  </div>
                  <span className="text-[11px] font-bold text-white bg-[#EE3B3B] px-3 py-1 rounded-full uppercase tracking-wide">
                    {caseData.condition?.replace(/_/g, " ")}
                  </span>
                </div>

                {/* Key Metrics Grid */}
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-[#FAFBFD] border border-[#F0F2F7] rounded-xl p-4 flex flex-col justify-between">
                    <span className="text-[10px] font-bold text-[#737A8F] uppercase tracking-wider">Estimated ETA</span>
                    <span className={`text-[22px] font-black mt-2 ${arrived ? "text-[#17B86B]" : "text-[#FFB21A]"}`}>
                      {arrived ? "ARRIVED" : `${eta ?? "—"} MIN`}
                    </span>
                  </div>
                  <div className="bg-[#FAFBFD] border border-[#F0F2F7] rounded-xl p-4 flex flex-col justify-between">
                    <span className="text-[10px] font-bold text-[#737A8F] uppercase tracking-wider">Travel Distance</span>
                    <span className="text-[22px] font-black text-[#1A1E2E] mt-2">
                      {caseData.distance_km ?? "—"} <span className="text-[12px] font-bold text-[#737A8F]">KM</span>
                    </span>
                  </div>
                  <div className="bg-[#FAFBFD] border border-[#F0F2F7] rounded-xl p-4 flex flex-col justify-between">
                    <span className="text-[10px] font-bold text-[#737A8F] uppercase tracking-wider">ML Match Score</span>
                    <span className="text-[22px] font-black mt-2" style={{ color: scoreColor(caseData.final_score) }}>
                      {scorePercent}%
                    </span>
                  </div>
                </div>

                {/* Match score bar */}
                <div className="mb-4">
                  <div className="flex justify-between text-[11px] font-semibold text-[#737A8F] mb-1.5">
                    <span>Dispatch Matching Quality</span>
                    <span style={{ color: scoreColor(caseData.final_score) }}>{scorePercent}% Confidence</span>
                  </div>
                  <div className="w-full bg-[#E2E8F0] h-2.5 rounded-full overflow-hidden">
                    <div
                      className="h-full transition-all duration-700 rounded-full"
                      style={{ width: `${scorePercent}%`, backgroundColor: scoreColor(caseData.final_score) }}
                    />
                  </div>
                </div>

                {/* Required Equipment */}
                {caseData.equipment_needed?.length > 0 && (
                  <div className="border-t border-[#F0F2F7] pt-4 mt-5">
                    <h4 className="text-[10px] font-extrabold text-[#737A8F] uppercase tracking-wider mb-2.5">
                      Required Patient Care Equipment
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {caseData.equipment_needed.map((eq, i) => (
                        <span key={i} className="text-[10.5px] font-bold text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-3 py-1 uppercase tracking-wide">
                          🛡️ {eq.replace(/_/g, " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Timeline Container (uses Light Theme variant) */}
              <div className="flex flex-col">
                <CaseTimeline caseId={case_id} role="hospital" theme="light" />
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-4">
                <button
                  onClick={handleMarkReady}
                  disabled={isReady}
                  className={`flex items-center justify-center gap-2 px-6 py-4 rounded-xl font-bold text-[13.5px] shadow-sm transition-all duration-200 border ${
                    isReady
                      ? "bg-[#E8FDF2] border-[#17B86B] text-[#17B86B] cursor-not-allowed font-extrabold"
                      : "bg-[#17B86B] border-[#149E5C] text-white hover:bg-[#149E5C] active:scale-[0.98]"
                  }`}
                >
                  {isReady ? "✓ Hospital Marked Ready" : "⚡ Mark Hospital Ready"}
                </button>
                <button
                  onClick={() => { window.location.href = "tel:112"; }}
                  className="flex items-center justify-center gap-2 px-6 py-4 rounded-xl font-bold text-[13.5px] bg-[#EE3B3B] border border-[#D32F2F] text-white hover:bg-[#D32F2F] shadow-sm transition active:scale-[0.98]"
                >
                  📞 Call Ambulance Dispatch
                </button>
              </div>

            </div>

            {/* Right Column (5/12 width on desktop) */}
            <div className="lg:col-span-5 flex flex-col gap-6">
              
              {/* Telemetry Map Container */}
              <div className="bg-white rounded-2xl border border-[#F0F2F7] shadow-sm overflow-hidden flex flex-col min-h-[450px] lg:h-[calc(100vh-200px)]">
                <div className="border-b border-[#F0F2F7] px-6 py-4 flex-shrink-0 flex items-center justify-between bg-white z-10">
                  <div className="flex items-center gap-2">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[#1A78F2] opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-[#1A78F2]"></span>
                    </span>
                    <h3 className="text-[13.5px] font-extrabold text-[#1A1E2E]">Live Ambulance Telemetry Map</h3>
                  </div>
                  <span className="text-[10px] font-bold text-[#737A8F] uppercase tracking-wider bg-[#F7F7FC] px-2.5 py-1 rounded-md">
                    🛰️ Active Route
                  </span>
                </div>
                <div className="flex-1 relative min-h-[350px]">
                  <Suspense fallback={<RouteFallback label="Loading hospital tracker map..." />}>
                    <MapWidget
                      variant="hospital"
                      hospitalPosition={hospPos}
                      ambulancePosition={ambPos}
                      caseData={caseData}
                      eta={eta}
                    />
                  </Suspense>
                </div>
              </div>

            </div>

          </div>
        </div>

      </main>

    </div>
  );
}
