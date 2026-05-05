import { useCallback, useEffect, useRef, useState } from "react";

function buildWsBase() {
  const env = import.meta.env.VITE_WS_URL;
  if (env) return env;
  const apiUrl = import.meta.env.VITE_API_URL || "";
  if (apiUrl) return apiUrl.replace(/^http/, "ws");
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
}

export default function useCaseSocket(caseId, enabled) {
  const wsRef = useRef(null);
  const [socketStatus, setSocketStatus] = useState("idle");
  const [lastEvent, setLastEvent] = useState(null);

  useEffect(() => {
    if (!enabled || !caseId) {
      setSocketStatus("idle");
      return undefined;
    }

    const token = localStorage.getItem("token");
    if (!token) {
      setSocketStatus("unauthorized");
      return undefined;
    }

    const ws = new WebSocket(`${buildWsBase()}/ws/track/${caseId}?token=${token}`);
    wsRef.current = ws;
    setSocketStatus("connecting");

    ws.onopen = () => setSocketStatus("live");
    ws.onerror = () => setSocketStatus("error");
    ws.onclose = () => setSocketStatus("closed");
    ws.onmessage = (event) => {
      try {
        setLastEvent(JSON.parse(event.data));
      } catch {
        // Ignore malformed server frames.
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [caseId, enabled]);

  const sendEvent = useCallback((payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
      return true;
    }
    return false;
  }, []);

  return { socketStatus, lastEvent, sendEvent };
}
