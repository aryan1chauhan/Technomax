import { createContext, useCallback, useContext, useState } from "react";

/* ── Context ─────────────────────────────────────────────────── */
const ToastCtx = createContext(null);

const ICONS = {
  success: "✅",
  error:   "❌",
  warning: "⚠️",
  info:    "ℹ️",
};

const ACCENT = {
  success: { border: "#17B86B", bg: "#E8FDF2", text: "#0E7A47" },
  error:   { border: "#EE3B3B", bg: "#FFEDED", text: "#C01C1C" },
  warning: { border: "#FFB21A", bg: "#FFF8E0", text: "#92600A" },
  info:    { border: "#1A78F2", bg: "#EBF3FF", text: "#0F4DA3" },
};

/* ── Provider ────────────────────────────────────────────────── */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id));
  }, []);

  const toast = useCallback(
    (message, type = "info", duration = 4000) => {
      const id = Date.now() + Math.random();
      setToasts((t) => [...t.slice(-4), { id, message, type }]); // max 5 visible
      if (duration > 0) setTimeout(() => dismiss(id), duration);
      return id;
    },
    [dismiss]
  );

  return (
    <ToastCtx.Provider value={{ toast, dismiss }}>
      {children}

      {/* ── Toast Stack ── */}
      <div
        aria-live="polite"
        className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2 items-end pointer-events-none"
      >
        {toasts.map(({ id, message, type }) => {
          const { border, bg, text } = ACCENT[type] || ACCENT.info;
          return (
            <div
              key={id}
              role="alert"
              className="pointer-events-auto flex items-start gap-3 rounded-xl border shadow-lg px-4 py-3 text-[13px] font-medium max-w-[340px] animate-in slide-in-from-right-4"
              style={{ borderColor: border, backgroundColor: bg, color: text }}
            >
              <span className="text-base leading-tight">{ICONS[type]}</span>
              <span className="flex-1 leading-snug">{message}</span>
              <button
                onClick={() => dismiss(id)}
                className="ml-1 opacity-50 hover:opacity-100 transition text-[16px] leading-none"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

/* ── Hook ────────────────────────────────────────────────────── */
export function useToast() {
  const ctx = useContext(ToastCtx);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
