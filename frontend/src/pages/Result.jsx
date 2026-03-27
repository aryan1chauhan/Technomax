// frontend/src/pages/Result.jsx
import { useLocation, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";

export default function Result() {
  const { state }  = useLocation();
  const navigate   = useNavigate();
  const [show, setShow] = useState(false);

  const result = state?.result;
  const ambLat = state?.lat;
  const ambLng = state?.lng;

  useEffect(() => {
    if (!result) { navigate("/dispatch"); return; }
    const t = setTimeout(() => setShow(true), 100);
    return () => clearTimeout(t);
  }, [result, navigate]);

  if (!result) return null;

  const score      = result.final_score ?? 0;
  const scorePct   = Math.round(score * 100);
  const scoreColor = scorePct > 70 ? "#17B86B" : scorePct > 40 ? "#FFB21A" : "#EE3B3B";
  const scoreBg    = scorePct > 70 ? "#E8FDF2" : scorePct > 40 ? "#FFF8E0" : "#FFEDED";

  const stats = [
    { val: `${result.distance_km ?? "—"} km`, label: "Distance" },
    { val: `${result.eta_minutes ?? "—"} min`, label: "ETA" },
    { val: result.beds ?? "—", label: "Beds Available" },
    { val: result.icu ?? "—", label: "ICU Beds" },
  ];

  return (
    <div className="min-h-screen bg-[#F7F7FC] font-['Inter',sans-serif]">

      {/* Nav */}
      <nav className="bg-white border-b border-[#F0F2F7] h-16 flex items-center px-8 gap-3">
        <div className="relative w-9 h-9 bg-[#17B86B] rounded-lg flex items-center justify-center">
          <span className="text-white text-lg font-bold">✓</span>
        </div>
        <div>
          <p className="text-[16px] font-bold text-[#1A1E2E] leading-none">MediRoute</p>
          <p className="text-[11px] text-[#737A8F]">Dispatch Result</p>
        </div>
      </nav>

      <div className={`max-w-[900px] mx-auto px-8 py-8 transition-all duration-500 ${show ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>

        {/* Success banner */}
        <div className="bg-[#E8FDF2] border-l-4 border-[#17B86B] rounded-xl px-6 py-4 mb-6 flex items-center gap-3">
          <span className="text-[#17B86B] text-lg">✓</span>
          <p className="text-[15px] font-semibold text-[#17B86B]">
            Best hospital identified — ML scored 188 candidates
          </p>
        </div>

        {/* Main card */}
        <div className="bg-white rounded-2xl border border-[#F0F2F7] overflow-hidden shadow-sm mb-6">
          {/* Top stripe */}
          <div className="h-1.5 bg-[#EE3B3B] w-full" />
          <div className="p-8">
            <p className="text-[11px] font-bold text-[#EE3B3B] tracking-widest mb-1">ASSIGNED HOSPITAL</p>
            <h2 className="text-[32px] font-bold text-[#1A1E2E]">{result.hospital_name}</h2>
            <p className="text-[14px] text-[#737A8F] mt-1 mb-6">{result.address}</p>

            {/* Score bar */}
            <div className="mb-6">
              <div className="flex items-center justify-between mb-2">
                <p className="text-[12px] text-[#737A8F]">ML Match Score</p>
                <span className="text-[15px] font-bold px-3 py-0.5 rounded-full" style={{ color: scoreColor, backgroundColor: scoreBg }}>
                  {scorePct}%
                </span>
              </div>
              <div className="h-2.5 bg-[#F0F2F7] rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{ width: `${scorePct}%`, backgroundColor: scoreColor }}
                />
              </div>
            </div>

            {/* Stats row */}
            <div className="grid grid-cols-4 gap-0 border border-[#F0F2F7] rounded-xl overflow-hidden mb-6">
              {stats.map(({ val, label }, i) => (
                <div key={label} className={`p-5 ${i < 3 ? "border-r border-[#F0F2F7]" : ""}`}>
                  <p className="text-[22px] font-bold text-[#1A1E2E]">{val}</p>
                  <p className="text-[12px] text-[#737A8F] mt-1">{label}</p>
                </div>
              ))}
            </div>

            {/* Equipment matched */}
            {result.equipment_matched?.length > 0 && (
              <div>
                <p className="text-[12px] text-[#737A8F] mb-2">Equipment Matched</p>
                <div className="flex flex-wrap gap-2">
                  {result.equipment_matched.map(eq => (
                    <span key={eq} className="bg-[#E8FDF2] text-[#17B86B] text-[11px] font-semibold px-3 py-1 rounded-full">
                      {eq.replace(/_/g, " ")} ✓
                    </span>
                  ))}
                  {result.equipment_missing?.map(eq => (
                    <span key={eq} className="bg-[#FFEDED] text-[#EE3B3B] text-[11px] font-semibold px-3 py-1 rounded-full">
                      {eq.replace(/_/g, " ")} ✗
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex gap-4 mb-6">
          <button
            onClick={() => navigate("/map", {
              state: {
                hospital: { lat: result.hospital_lat, lng: result.hospital_lng, name: result.hospital_name },
                caseId: result.case_id,
                ambLat, ambLng,
              },
            })}
            className="flex-1 h-[56px] bg-[#1A78F2] hover:bg-[#1259C8] text-white font-bold text-[15px] rounded-xl transition"
          >
            🗺&nbsp; Open Navigation Map
          </button>
          <button
            onClick={() => navigate("/dispatch")}
            className="h-[56px] px-6 bg-white border border-[#C7CCD9] text-[#737A8F] hover:text-[#1A1E2E] font-medium text-[14px] rounded-xl transition"
          >
            ← New Dispatch
          </button>
        </div>

        {/* ML Reasoning */}
        {result.ml_reasoning?.length > 0 && (
          <div className="bg-white rounded-xl border border-[#F0F2F7] p-6">
            <p className="text-[14px] font-bold text-[#1A1E2E] mb-3">Why this hospital?</p>
            <ul className="space-y-2">
              {result.ml_reasoning.map((line, i) => (
                <li key={i} className="text-[13px] text-[#737A8F] flex gap-2">
                  <span className="text-[#1A78F2] font-bold">•</span> {line}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
