import { useEffect, useState } from "react";
import api from "../api/axios";

/**
 * BackendWakeUp — silently pings /health every 3 s.
 * Shows a non-blocking warm-up banner only if the first ping takes > 2 s
 * (indicating a Render free-tier cold start).  Disappears once the backend
 * responds or after 90 s (timeout).
 */
export default function BackendWakeUp() {
  const [show, setShow]       = useState(false);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    let ticker = null;
    let mounted = true;

    const ping = async () => {
      const start = Date.now();
      try {
        await api.get("/health", { timeout: 90_000 });
        if (mounted) setShow(false);
      } catch {
        // still waking up — keep trying
        if (mounted) setTimeout(ping, 3000);
      }
      const took = Date.now() - start;
      // Only show the banner if first response took > 2 s (cold start)
      if (took > 2000 && mounted) setShow(true);
    };

    // Delay first ping by 1 s so fast loads never flash the banner
    const initial = setTimeout(() => {
      ping();
      ticker = setInterval(() => {
        setElapsed((e) => {
          if (e >= 90) { clearInterval(ticker); setShow(false); }
          return e + 1;
        });
      }, 1000);
    }, 1000);

    return () => {
      mounted = false;
      clearTimeout(initial);
      clearInterval(ticker);
    };
  }, []);

  if (!show) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed top-4 left-1/2 -translate-x-1/2 z-[9998] flex items-center gap-3 bg-[#0D1830] border border-[#1A78F2]/40 text-[#C7CCD9] text-[13px] font-medium px-5 py-3 rounded-xl shadow-xl"
    >
      <span className="w-3 h-3 rounded-full bg-[#1A78F2] animate-pulse flex-shrink-0" />
      <span>
        Server is waking up — this may take up to 60 s on the free tier
        {elapsed > 5 ? ` (${elapsed}s…)` : ""}
      </span>
    </div>
  );
}
