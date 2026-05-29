import { useState, useEffect, useRef, useCallback } from "react";
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Radio,
  AlertCircle,
  Loader,
} from "lucide-react";

// ─── ICE Servers (STUN only — swap for TURN in production) ─────────────────
const ICE_SERVERS = {
  iceServers: [
    { urls: "stun:stun.l.google.com:19302" },
    { urls: "stun:stun1.l.google.com:19302" },
  ],
};

// ─── Call States ────────────────────────────────────────────────────────────
const CALL_STATE = {
  IDLE: "idle",
  CALLING: "calling",   // outgoing — waiting for answer
  RINGING: "ringing",   // incoming — waiting for local accept
  CONNECTED: "connected",
  ENDED: "ended",
  ERROR: "error",
};

/**
 * CallPanel — WebRTC voice call panel for MediRoute
 *
 * Props:
 *   socket       {WebSocket}  — active case WebSocket (already open)
 *   caseId       {string}     — current dispatch case ID
 *   role         {string}     — "paramedic" | "hospital"
 *   remoteLabel  {string}     — display name of the other party
 *   onClose      {function}   — called when panel should unmount
 */
export default function CallPanel({ socket, caseId, role, remoteLabel = "Remote", onClose }) {
  const [callState, setCallState] = useState(CALL_STATE.IDLE);
  const [isMuted, setIsMuted]     = useState(false);
  const [isSpeaker, setIsSpeaker] = useState(true);
  const [duration, setDuration]   = useState(0);
  const [error, setError]         = useState(null);

  const pcRef           = useRef(null);   // RTCPeerConnection
  const localStreamRef  = useRef(null);   // local MediaStream
  const remoteAudioRef  = useRef(null);   // <audio> element for remote audio
  const timerRef        = useRef(null);
  const pendingCandidatesRef = useRef([]); // ICE candidates queued before remoteDesc is set

  // ── Helpers ───────────────────────────────────────────────────────────────

  const sendSignal = useCallback((type, payload) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ type, case_id: caseId, ...payload }));
  }, [socket, caseId]);

  const cleanup = useCallback(() => {
    clearInterval(timerRef.current);
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((t) => t.stop());
      localStreamRef.current = null;
    }
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    pendingCandidatesRef.current = [];
    setDuration(0);
  }, []);

  // ── Build RTCPeerConnection ───────────────────────────────────────────────

  const buildPeerConnection = useCallback(() => {
    const pc = new RTCPeerConnection(ICE_SERVERS);

    // Send ICE candidates to remote peer via WebSocket
    pc.onicecandidate = ({ candidate }) => {
      if (candidate) {
        sendSignal("webrtc_ice_candidate", { candidate: candidate.toJSON() });
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "connected") {
        setCallState(CALL_STATE.CONNECTED);
        timerRef.current = setInterval(() => setDuration((d) => d + 1), 1000);
      }
      if (["disconnected", "failed", "closed"].includes(pc.connectionState)) {
        setCallState(CALL_STATE.ENDED);
        cleanup();
      }
    };

    // Attach incoming remote audio track to the <audio> element
    pc.ontrack = ({ streams }) => {
      if (remoteAudioRef.current && streams[0]) {
        remoteAudioRef.current.srcObject = streams[0];
      }
    };

    return pc;
  }, [sendSignal, cleanup]);

  // ── Get local microphone ─────────────────────────────────────────────────

  const getLocalStream = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    localStreamRef.current = stream;
    return stream;
  }, []);

  // ── Initiate outgoing call (Paramedic → Hospital) ────────────────────────

  const startCall = useCallback(async () => {
    try {
      setError(null);
      setCallState(CALL_STATE.CALLING);

      const stream = await getLocalStream();
      const pc = buildPeerConnection();
      pcRef.current = pc;

      // Add local audio tracks to peer connection
      stream.getTracks().forEach((track) => pc.addTrack(track, stream));

      // Create SDP offer and send to remote
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      sendSignal("webrtc_offer", { sdp: pc.localDescription });
    } catch (err) {
      setError("Microphone access denied or call failed.");
      setCallState(CALL_STATE.ERROR);
      cleanup();
    }
  }, [getLocalStream, buildPeerConnection, sendSignal, cleanup]);

  // ── Accept incoming call (Hospital side) ─────────────────────────────────

  const acceptCall = useCallback(async (offerSdp) => {
    try {
      setError(null);
      const stream = await getLocalStream();
      const pc = buildPeerConnection();
      pcRef.current = pc;

      stream.getTracks().forEach((track) => pc.addTrack(track, stream));

      await pc.setRemoteDescription(new RTCSessionDescription(offerSdp));

      // Flush any ICE candidates that arrived before remoteDescription was set
      for (const c of pendingCandidatesRef.current) {
        await pc.addIceCandidate(new RTCIceCandidate(c));
      }
      pendingCandidatesRef.current = [];

      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSignal("webrtc_answer", { sdp: pc.localDescription });
      setCallState(CALL_STATE.CONNECTED);
    } catch (err) {
      setError("Failed to accept call.");
      setCallState(CALL_STATE.ERROR);
      cleanup();
    }
  }, [getLocalStream, buildPeerConnection, sendSignal, cleanup]);

  // ── Hang up ───────────────────────────────────────────────────────────────

  const hangUp = useCallback(() => {
    sendSignal("webrtc_hangup", {});
    setCallState(CALL_STATE.ENDED);
    cleanup();
  }, [sendSignal, cleanup]);

  // ── WebSocket message handler ─────────────────────────────────────────────

  useEffect(() => {
    if (!socket) return;

    const handleMessage = async (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.case_id && msg.case_id !== caseId) return;

      switch (msg.type) {
        // Incoming call — show ringing UI, store offer for acceptCall()
        case "webrtc_offer": {
          if (role === "paramedic") return; // paramedic is always caller
          setCallState(CALL_STATE.RINGING);
          // Store offer SDP on accept button click
          pcRef._pendingOffer = msg.sdp;
          break;
        }

        // Remote answered our offer
        case "webrtc_answer": {
          if (!pcRef.current) return;
          await pcRef.current.setRemoteDescription(new RTCSessionDescription(msg.sdp));
          // Flush pending ICE candidates
          for (const c of pendingCandidatesRef.current) {
            await pcRef.current.addIceCandidate(new RTCIceCandidate(c));
          }
          pendingCandidatesRef.current = [];
          break;
        }

        // Remote ICE candidate
        case "webrtc_ice_candidate": {
          if (!pcRef.current || !pcRef.current.remoteDescription) {
            // Queue if remote description isn't set yet
            pendingCandidatesRef.current.push(msg.candidate);
          } else {
            await pcRef.current.addIceCandidate(new RTCIceCandidate(msg.candidate));
          }
          break;
        }

        // Remote hung up
        case "webrtc_hangup": {
          setCallState(CALL_STATE.ENDED);
          cleanup();
          break;
        }

        default: break;
      }
    };

    socket.addEventListener("message", handleMessage);
    return () => socket.removeEventListener("message", handleMessage);
  }, [socket, caseId, role, cleanup]);

  // ── Mute / Speaker toggles ────────────────────────────────────────────────

  const toggleMute = () => {
    if (!localStreamRef.current) return;
    localStreamRef.current.getAudioTracks().forEach((t) => { t.enabled = isMuted; });
    setIsMuted((m) => !m);
  };

  const toggleSpeaker = () => {
    if (remoteAudioRef.current) {
      remoteAudioRef.current.muted = isSpeaker;
    }
    setIsSpeaker((s) => !s);
  };

  // ── Cleanup on unmount ────────────────────────────────────────────────────

  useEffect(() => () => cleanup(), [cleanup]);

  // ── Duration formatter ────────────────────────────────────────────────────

  const formatDuration = (s) => {
    const m = Math.floor(s / 60).toString().padStart(2, "0");
    const sec = (s % 60).toString().padStart(2, "0");
    return `${m}:${sec}`;
  };

  // ─────────────────────────────────────────────────────────────────────────
  // UI
  // ─────────────────────────────────────────────────────────────────────────

  return (
    <div style={styles.overlay}>
      {/* Hidden audio element — plays remote peer's voice */}
      <audio ref={remoteAudioRef} autoPlay playsInline style={{ display: "none" }} />

      <div style={styles.panel}>
        {/* Header */}
        <div style={styles.header}>
          <div style={styles.radioIcon}>
            <Radio size={14} color="#ef4444" />
          </div>
          <span style={styles.headerLabel}>MEDIROUTE SECURE CHANNEL</span>
        </div>

        {/* Remote party info */}
        <div style={styles.callerSection}>
          <div style={styles.avatar}>
            {remoteLabel.charAt(0).toUpperCase()}
          </div>
          <div style={styles.callerName}>{remoteLabel}</div>
          <div style={styles.callStatus}>
            {callState === CALL_STATE.IDLE      && <span style={styles.statusText}>Ready to call</span>}
            {callState === CALL_STATE.CALLING   && <span style={styles.statusPulse}>Calling…</span>}
            {callState === CALL_STATE.RINGING   && <span style={styles.statusPulse}>Incoming call…</span>}
            {callState === CALL_STATE.CONNECTED && (
              <span style={styles.statusConnected}>
                <span style={styles.greenDot} /> {formatDuration(duration)}
              </span>
            )}
            {callState === CALL_STATE.ENDED     && <span style={styles.statusText}>Call ended</span>}
            {callState === CALL_STATE.ERROR     && (
              <span style={styles.statusError}>
                <AlertCircle size={12} style={{ marginRight: 4 }} /> {error}
              </span>
            )}
          </div>
        </div>

        {/* Controls */}
        <div style={styles.controls}>
          {/* Mute */}
          {callState === CALL_STATE.CONNECTED && (
            <button
              style={{ ...styles.controlBtn, ...(isMuted ? styles.controlBtnActive : {}) }}
              onClick={toggleMute}
              title={isMuted ? "Unmute" : "Mute"}
            >
              {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
            </button>
          )}

          {/* Speaker */}
          {callState === CALL_STATE.CONNECTED && (
            <button
              style={{ ...styles.controlBtn, ...(!isSpeaker ? styles.controlBtnActive : {}) }}
              onClick={toggleSpeaker}
              title={isSpeaker ? "Mute speaker" : "Unmute speaker"}
            >
              {isSpeaker ? <Volume2 size={18} /> : <VolumeX size={18} />}
            </button>
          )}

          {/* Main action button */}
          {(callState === CALL_STATE.IDLE || callState === CALL_STATE.ENDED || callState === CALL_STATE.ERROR) && role === "paramedic" && (
            <button style={styles.callBtn} onClick={startCall}>
              <Phone size={22} />
            </button>
          )}

          {callState === CALL_STATE.CALLING && (
            <button style={{ ...styles.callBtn, ...styles.hangupBtn }} onClick={hangUp}>
              <Loader size={18} style={styles.spin} />
            </button>
          )}

          {callState === CALL_STATE.RINGING && (
            <>
              <button style={styles.callBtn} onClick={() => acceptCall(pcRef._pendingOffer)}>
                <Phone size={22} />
              </button>
              <button style={{ ...styles.callBtn, ...styles.hangupBtn }} onClick={hangUp}>
                <PhoneOff size={22} />
              </button>
            </>
          )}

          {callState === CALL_STATE.CONNECTED && (
            <button style={{ ...styles.callBtn, ...styles.hangupBtn }} onClick={hangUp}>
              <PhoneOff size={22} />
            </button>
          )}
        </div>

        {/* Close */}
        {[CALL_STATE.IDLE, CALL_STATE.ENDED, CALL_STATE.ERROR].includes(callState) && (
          <button style={styles.closeBtn} onClick={() => { cleanup(); onClose?.(); }}>
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Styles ──────────────────────────────────────────────────────────────────

const styles = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.6)",
    backdropFilter: "blur(4px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 9999,
  },
  panel: {
    background: "#0f172a",
    border: "1px solid #1e293b",
    borderRadius: "16px",
    padding: "28px 32px",
    width: "320px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "20px",
    boxShadow: "0 25px 60px rgba(0,0,0,0.6)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  radioIcon: {
    background: "rgba(239,68,68,0.15)",
    borderRadius: "50%",
    padding: "4px",
    display: "flex",
  },
  headerLabel: {
    fontSize: "10px",
    letterSpacing: "0.12em",
    color: "#64748b",
    fontFamily: "monospace",
    fontWeight: 600,
  },
  callerSection: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "10px",
  },
  avatar: {
    width: "68px",
    height: "68px",
    borderRadius: "50%",
    background: "linear-gradient(135deg, #1d4ed8, #0ea5e9)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "26px",
    fontWeight: 700,
    color: "#fff",
    boxShadow: "0 0 0 4px rgba(14,165,233,0.15)",
  },
  callerName: {
    fontSize: "18px",
    fontWeight: 600,
    color: "#f1f5f9",
    letterSpacing: "-0.01em",
  },
  callStatus: {
    fontSize: "13px",
    color: "#94a3b8",
    display: "flex",
    alignItems: "center",
    gap: "4px",
  },
  statusText:      { color: "#64748b" },
  statusPulse:     { color: "#f59e0b", animation: "pulse 1.5s infinite" },
  statusConnected: { color: "#22c55e", display: "flex", alignItems: "center", gap: "6px", fontVariantNumeric: "tabular-nums" },
  statusError:     { color: "#ef4444", display: "flex", alignItems: "center" },
  greenDot: {
    width: "8px",
    height: "8px",
    borderRadius: "50%",
    background: "#22c55e",
    boxShadow: "0 0 6px #22c55e",
    display: "inline-block",
  },
  controls: {
    display: "flex",
    gap: "14px",
    alignItems: "center",
    justifyContent: "center",
  },
  controlBtn: {
    width: "44px",
    height: "44px",
    borderRadius: "50%",
    background: "#1e293b",
    border: "1px solid #334155",
    color: "#94a3b8",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    transition: "all 0.15s",
  },
  controlBtnActive: {
    background: "#334155",
    color: "#f1f5f9",
    borderColor: "#475569",
  },
  callBtn: {
    width: "56px",
    height: "56px",
    borderRadius: "50%",
    background: "#16a34a",
    border: "none",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    cursor: "pointer",
    boxShadow: "0 4px 20px rgba(22,163,74,0.4)",
    transition: "transform 0.1s, box-shadow 0.1s",
  },
  hangupBtn: {
    background: "#dc2626",
    boxShadow: "0 4px 20px rgba(220,38,38,0.4)",
  },
  spin: {
    animation: "spin 1s linear infinite",
  },
  closeBtn: {
    background: "transparent",
    border: "none",
    color: "#475569",
    fontSize: "12px",
    cursor: "pointer",
    letterSpacing: "0.05em",
    textTransform: "uppercase",
    fontFamily: "monospace",
  },
};
