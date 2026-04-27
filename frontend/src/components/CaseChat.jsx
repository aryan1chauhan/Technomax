import React, { useEffect, useMemo, useState } from "react";
import api from "../api/axios";

function mergeMessages(existing, incoming) {
  const byId = new Map(existing.map((message) => [message.id, message]));
  incoming.forEach((message) => {
    byId.set(message.id, message);
  });
  return [...byId.values()].sort((a, b) => new Date(a.sent_at) - new Date(b.sent_at));
}

export default function CaseChat({ caseId, caseLabel, socketEvent }) {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadMessages() {
      setLoading(true);
      setError("");
      try {
        const res = await api.get(`/api/cases/${caseId}/messages`, { params: { limit: 50, page: 1 } });
        if (active) {
          setMessages(res.data.items || []);
        }
      } catch (err) {
        if (active) {
          setError(err?.response?.data?.detail || "Could not load chat history.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    loadMessages();
    return () => {
      active = false;
    };
  }, [caseId]);

  useEffect(() => {
    if (socketEvent?.type !== "chat" || socketEvent.case_id !== caseId || !socketEvent.message) return;
    setMessages((prev) => mergeMessages(prev, [socketEvent.message]));
  }, [caseId, socketEvent]);

  const emptyState = useMemo(() => !loading && messages.length === 0, [loading, messages.length]);

  const handleSend = async () => {
    const body = draft.trim();
    if (!body) return;

    setSending(true);
    setError("");
    try {
      const res = await api.post(`/api/cases/${caseId}/messages`, { body });
      setMessages((prev) => mergeMessages(prev, [res.data]));
      setDraft("");
    } catch (err) {
      setError(err?.response?.data?.detail || "Could not send message.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-[#E2E6F0] shadow-sm p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <p className="text-[15px] font-bold text-[#1A1E2E]">Case Chat</p>
          <p className="text-[12px] text-[#737A8F]">{caseLabel || `Case #${caseId}`}</p>
        </div>
        <span className="text-[11px] uppercase tracking-wide text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-3 py-1">
          Live
        </span>
      </div>

      <div className="bg-[#F7F7FC] border border-[#EEF1F7] rounded-xl p-3 h-[280px] overflow-y-auto space-y-3">
        {loading && <p className="text-[13px] text-[#737A8F]">Loading messages...</p>}
        {emptyState && <p className="text-[13px] text-[#737A8F]">No messages yet. Start the case conversation.</p>}
        {messages.map((message) => (
          <div key={message.id} className="bg-white rounded-xl border border-[#E2E6F0] px-3 py-2">
            <div className="flex items-center justify-between gap-3 mb-1">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-[#1A78F2]">
                {message.sender_role}
              </span>
              <span className="text-[11px] text-[#9EA6BC]">
                {new Date(message.sent_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
            <p className="text-[13px] text-[#1A1E2E] leading-relaxed">{message.body}</p>
          </div>
        ))}
      </div>

      {error && <p className="mt-3 text-[12px] text-[#EE3B3B]">{error}</p>}

      <div className="mt-4 flex gap-3">
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Type a message for the case team..."
          rows={2}
          className="flex-1 resize-none rounded-xl border border-[#D0D5E8] px-3 py-2 text-[13px] outline-none text-[#1A1E2E]"
        />
        <button
          onClick={handleSend}
          disabled={sending || !draft.trim()}
          className="self-end rounded-xl bg-[#1A78F2] px-4 py-2 text-[13px] font-semibold text-white disabled:opacity-60"
        >
          {sending ? "Sending..." : "Send"}
        </button>
      </div>
    </div>
  );
}
