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

export default function CaseTimeline({ caseId, role, theme }) {
  const [events, setEvents] = useState([]);
  const [currentStatus, setCurrentStatus] = useState("dispatched");
  const [error, setError] = useState("");

  const isLight = theme === "light";
  const bg = isLight ? "#ffffff" : "#1e293b";
  const border = isLight ? "1px solid #f0f2f7" : "1px solid #334155";
  const titleColor = isLight ? "#1a1e2e" : "#f1f5f9";
  const lineColor = isLight ? "#e2e8f0" : "#334155";
  const errorBg = isLight ? "rgba(239, 68, 68, 0.05)" : "rgba(239, 68, 68, 0.1)";
  const errorBorder = isLight ? "rgba(239, 68, 68, 0.15)" : "rgba(239, 68, 68, 0.3)";
  const errorText = isLight ? "#ef4444" : "#fca5a5";

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
    <div style={{
      background: bg,
      border: border,
      borderRadius: "16px",
      padding: "24px",
      marginBottom: "24px",
      boxShadow: isLight ? "0 1px 3px 0 rgba(0, 0, 0, 0.05)" : "none",
    }}>
      <h3 style={{
        fontSize: "15px",
        fontWeight: "700",
        color: titleColor,
        marginBottom: "20px",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        fontFamily: "Inter, system-ui, -apple-system, sans-serif"
      }}>
        ⏱ Case Timeline
      </h3>
      
      {error && (
        <div style={{
          background: errorBg,
          border: errorBorder,
          color: errorText,
          padding: "12px",
          borderRadius: "8px",
          marginBottom: "16px",
          fontSize: "13px",
          fontWeight: "500",
        }}>
          {error}
        </div>
      )}

      {/* Timeline items list */}
      <div style={{ position: "relative", paddingLeft: "24px" }}>
        {/* Connecting Vertical Line */}
        {events.length > 1 && (
          <div style={{
            position: "absolute",
            left: "6px",
            top: "10px",
            bottom: "10px",
            width: "2px",
            background: lineColor,
          }} />
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {events.map((ev, i) => {
            const formattedDate = new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + " · " + new Date(ev.timestamp).toLocaleDateString([], { day: '2-digit', month: 'short' });
            const isLatest = i === events.length - 1;
            
            // Tag styling by role
            let tagBg = isLight ? "rgba(115, 122, 143, 0.08)" : "rgba(148, 163, 184, 0.1)";
            let tagColor = isLight ? "#737a8f" : "#cbd5e1";
            let tagBorder = isLight ? "rgba(115, 122, 143, 0.15)" : "rgba(148, 163, 184, 0.2)";
            if (ev.actor_role === "ambulance") {
              tagBg = "rgba(26, 120, 242, 0.08)";
              tagColor = "#1a78f2";
              tagBorder = "rgba(26, 120, 242, 0.15)";
            } else if (ev.actor_role === "hospital") {
              tagBg = "rgba(167, 139, 250, 0.08)";
              tagColor = "#a78bfa";
              tagBorder = "rgba(167, 139, 250, 0.15)";
            }

            return (
              <div key={ev.id} style={{ position: "relative", display: "flex", gap: "16px", alignItems: "flex-start" }}>
                {/* Timeline Dot */}
                <div style={{
                  position: "absolute",
                  left: "-23px",
                  top: "6px",
                  width: "12px",
                  height: "12px",
                  borderRadius: "50%",
                  background: isLatest ? "#10b981" : (isLight ? "#cbd5e1" : "#475569"),
                  border: isLatest ? "3px solid rgba(16, 185, 129, 0.3)" : (isLight ? "3px solid #f8fafc" : "3px solid rgba(71, 85, 105, 0.3)"),
                  zIndex: 2,
                  boxSizing: "content-box",
                }} />

                {/* Event Details Card */}
                <div style={{
                  flex: 1,
                  display: "flex",
                  flexDirection: "column",
                  gap: "6px",
                }}>
                  <div style={{ display: "flex", justifycontent: "space-between", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{
                      fontWeight: "700",
                      fontSize: "14px",
                      color: isLatest ? "#10b981" : (isLight ? "#1a1e2e" : "#f1f5f9"),
                      textTransform: "capitalize",
                      fontFamily: "Inter, system-ui, -apple-system, sans-serif"
                    }}>
                      {ev.status.replace(/_/g, ' ')}
                    </span>
                    <time style={{
                      fontSize: "11px",
                      color: isLight ? "#737a8f" : "#64748b",
                      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
                    }}>
                      {formattedDate}
                    </time>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                    <span style={{
                      fontSize: "9px",
                      fontWeight: "705",
                      fontWeight: "bold",
                      textTransform: "uppercase",
                      letterSpacing: "0.08em",
                      background: tagBg,
                      color: tagColor,
                      border: `1px solid ${tagBorder}`,
                      padding: "2px 6px",
                      borderRadius: "4px",
                      fontFamily: "Inter, system-ui, -apple-system, sans-serif",
                    }}>
                      {ev.actor_role}
                    </span>
                    {ev.note && (
                      <span style={{
                        fontSize: "13px",
                        color: isLight ? "#404454" : "#94a3b8",
                        fontFamily: "Inter, system-ui, -apple-system, sans-serif",
                      }}>
                        {ev.note}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {!isTerminal && (
        <div style={{
          marginTop: "24px",
          display: "flex",
          gap: "12px",
          paddingTop: "16px",
          borderTop: isLight ? "1px solid #f0f2f7" : "1px solid #334155",
        }}>
          {nextLabel && (
            <button
              onClick={() => updateStatus(nextVal)}
              disabled={!nextVal}
              style={{
                flex: 1,
                height: "44px",
                fontFamily: "Inter, system-ui, -apple-system, sans-serif",
                fontWeight: "700",
                fontSize: "13px",
                borderRadius: "8px",
                cursor: nextVal ? "pointer" : "not-allowed",
                background: nextVal ? "#10b981" : (isLight ? "#f0f2f7" : "rgba(71, 85, 105, 0.2)"),
                border: nextVal ? "1px solid rgba(16, 185, 129, 0.4)" : (isLight ? "1px solid #e2e8f0" : "1px solid rgba(71, 85, 105, 0.3)"),
                color: nextVal ? "#ffffff" : (isLight ? "#737a8f" : "#475569"),
                transition: "all 0.2s ease",
              }}
            >
              {nextLabel}
            </button>
          )}
          <button
            onClick={() => updateStatus("cancelled")}
            style={{
              height: "44px",
              padding: "0 20px",
              fontFamily: "Inter, system-ui, -apple-system, sans-serif",
              fontWeight: "600",
              fontSize: "13px",
              borderRadius: "8px",
              background: isLight ? "#fff5f5" : "transparent",
              border: isLight ? "1px solid #fca5a5" : "1px solid rgba(239, 68, 68, 0.4)",
              color: "#ef4444",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            Cancel Case
          </button>
        </div>
      )}
      
      {currentStatus === "completed" && (
         <div style={{
           marginTop: "20px",
           background: isLight ? "#ecfdf5" : "rgba(16, 185, 129, 0.1)",
           border: isLight ? "1px solid #a7f3d0" : "1px solid rgba(16, 185, 129, 0.3)",
           color: "#10b981",
           padding: "12px",
           borderRadius: "8px",
           textAlign: "center",
           fontWeight: "700",
           fontSize: "14px",
           fontFamily: "Inter, system-ui, -apple-system, sans-serif",
         }}>
           Case Closed Successfully
         </div>
      )}
    </div>
  );
}
