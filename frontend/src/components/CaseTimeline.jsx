import { useState, useEffect, useCallback } from "react";
import api from "../api/axios";

const getValidNextTransitionLabel = (role, currentStatus) => {
  if (role === "ambulance") {
    switch (currentStatus) {
      case "dispatched": return ["Start Journey", "en_route"];
      case "en_route": return ["Arrived at Scene", "on_scene"];
      case "on_scene": return ["Patient Loaded", "transporting"];
      case "transporting": return ["At Hospital", "arrived"];
      case "arrived": return ["Mark Complete", "completed"];
      default: return null;
    }
  } else if (role === "hospital") {
    // Hospital CANNOT click "Start Journey" or "Arrived at Scene"
    switch (currentStatus) {
      case "dispatched": return ["Start Journey (Ambulance Only)", null];
      case "en_route": return ["Arrived at Scene (Ambulance Only)", null];
      case "on_scene": return ["Patient Loaded (Ambulance Only)", null];
      case "transporting": return ["Confirm Ready", "arrived"];
      case "arrived": return ["Complete Case", "completed"];
      default: return null;
    }
  }
  return null;
}

export default function CaseTimeline({ caseId, role }) {
  const [events, setEvents] = useState([]);
  const [currentStatus, setCurrentStatus] = useState("dispatched");
  const [error, setError] = useState("");

  const fetchTimeline = useCallback(async () => {
    try {
      const res = await api.get(`/api/cases/${caseId}/timeline`);
      const data = res.data;
      setEvents(data);
      if (data.length > 0) {
        setCurrentStatus(data[data.length - 1].status);
      }
    } catch (err) {
      console.error("Failed to fetch timeline", err);
    }
  }, [caseId]);

  useEffect(() => {
    const initialFetchTimer = setTimeout(() => {
      fetchTimeline();
    }, 0);

    if (currentStatus === "completed" || currentStatus === "cancelled") {
      return () => clearTimeout(initialFetchTimer);
    }

    const interval = setInterval(() => {
      if (currentStatus !== "completed" && currentStatus !== "cancelled") {
        fetchTimeline();
      }
    }, 15000);

    return () => {
      clearTimeout(initialFetchTimer);
      clearInterval(interval);
    };
  }, [currentStatus, fetchTimeline]);

  const updateStatus = async (newStatus) => {
    try {
      const payload = { status: newStatus };
      
      if (newStatus === "arrived" && events.length > 0) {
        const dispatchEvent = events.find(e => e.status === "dispatched");
        if (dispatchEvent) {
          payload.actual_eta_minutes = Math.round((Date.now() - new Date(dispatchEvent.timestamp).getTime()) / 60000);
        }
      }

      await api.put(`/api/cases/${caseId}/status`, payload);
      fetchTimeline();
      setError("");
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || "Failed to update status");
    }
  };

  const isTerminal = currentStatus === "completed" || currentStatus === "cancelled";
  const transitionInfo = getValidNextTransitionLabel(role, currentStatus);
  const nextLabel = transitionInfo ? transitionInfo[0] : null;
  const nextVal = transitionInfo ? transitionInfo[1] : null;

  return (
    <div className="bg-white rounded-2xl border border-[#F0F2F7] overflow-hidden shadow-sm mb-6 p-8">
      <h3 className="text-[18px] font-bold text-[#1A1E2E] mb-6 flex items-center gap-2">⏱ Case Timeline</h3>
      
      {error && (
        <div className="bg-[#FFEDED] text-[#EE3B3B] p-3 rounded-lg mb-4 text-[13px] font-medium">
          {error}
        </div>
      )}

      <div className="space-y-6 relative before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-slate-300 before:to-transparent">
        {events.map((ev, i) => {
          const formattedDate = new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " · " + new Date(ev.timestamp).toLocaleDateString([], { day: '2-digit', month: 'short' });
          return (
            <div key={ev.id} className="relative flex items-center justify-between md:justify-normal md:odd:flex-row-reverse group is-active">
              <div className={"flex items-center justify-center w-10 h-10 rounded-full border border-white bg-slate-200 text-slate-500 shadow shrink-0 md:order-1 md:group-odd:-translate-x-1/2 md:group-even:translate-x-1/2 " + (i === events.length - 1 ? 'bg-[#1A78F2] text-white' : '')}>
                {i + 1}
              </div>
              <div className="w-[calc(100%-4rem)] md:w-[calc(50%-2.5rem)] bg-slate-50 p-4 rounded border border-slate-200 shadow-sm">
                <div className="flex items-center justify-between space-x-2 mb-1">
                  <div className="font-bold text-slate-900 capitalize">{ev.status.replace(/_/g, ' ')}</div>
                  <time className="font-caveat font-medium text-slate-500 text-xs">{formattedDate}</time>
                </div>
                <div className="text-slate-500 text-sm">
                  <span className="text-[11px] uppercase bg-slate-200 px-2 py-0.5 rounded mr-2">{ev.actor_role}</span>
                  {ev.note && <span>{ev.note}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {!isTerminal && (
        <div className="mt-8 flex gap-4 pt-4 border-t border-[#F0F2F7]">
          {nextLabel && (
            <button
              onClick={() => updateStatus(nextVal)}
              disabled={!nextVal}
              className={`flex-1 h-[48px] font-bold text-[14px] rounded-xl transition ${nextVal ? 'bg-[#17B86B] hover:bg-[#14a35f] text-white' : 'bg-gray-200 text-gray-500 cursor-not-allowed'}`}
            >
              {nextLabel}
            </button>
          )}
          <button
            onClick={() => updateStatus("cancelled")}
            className="h-[48px] px-6 bg-white border border-[#EE3B3B] text-[#EE3B3B] hover:bg-[#EE3B3B] hover:text-white font-medium text-[14px] rounded-xl transition"
          >
            Cancel Case
          </button>
        </div>
      )}
      
      {currentStatus === "completed" && (
         <div className="mt-6 bg-[#E8FDF2] border border-[#17B86B] text-[#17B86B] p-4 rounded-xl text-center font-bold">
           Case Closed Successfully
         </div>
      )}
    </div>
  );
}
