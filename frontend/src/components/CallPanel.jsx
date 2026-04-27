import React, { useEffect, useRef, useState } from "react";

const RTC_CONFIGURATION = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

export default function CallPanel({ caseId, caseLabel, socketEvent, sendEvent, socketStatus }) {
  const [callState, setCallState] = useState("idle");
  const [statusText, setStatusText] = useState("Ready to start a case call.");
  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const localStreamRef = useRef(null);
  const remoteStreamRef = useRef(null);
  const peerRef = useRef(null);
  const pendingOfferRef = useRef(null);
  const pendingIceRef = useRef([]);
  const timeoutRef = useRef(null);

  const clearNoAnswerTimer = () => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const cleanupCall = (nextState = "idle", nextStatus = "Ready to start a case call.") => {
    clearNoAnswerTimer();
    pendingOfferRef.current = null;
    pendingIceRef.current = [];

    if (peerRef.current) {
      peerRef.current.onicecandidate = null;
      peerRef.current.ontrack = null;
      peerRef.current.onconnectionstatechange = null;
      peerRef.current.close();
      peerRef.current = null;
    }

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
      localStreamRef.current = null;
    }

    if (remoteStreamRef.current) {
      remoteStreamRef.current.getTracks().forEach((track) => track.stop());
      remoteStreamRef.current = null;
    }

    if (localVideoRef.current) localVideoRef.current.srcObject = null;
    if (remoteVideoRef.current) remoteVideoRef.current.srcObject = null;

    setCallState(nextState);
    setStatusText(nextStatus);
  };

  const startNoAnswerTimer = () => {
    clearNoAnswerTimer();
    timeoutRef.current = setTimeout(() => {
      sendEvent({ type: "call_end" });
      cleanupCall("no_answer", "No answer after 30 seconds.");
    }, 30000);
  };

  const ensureLocalStream = async () => {
    if (localStreamRef.current) return localStreamRef.current;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
    localStreamRef.current = stream;
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = stream;
    }
    return stream;
  };

  const flushPendingIce = async () => {
    if (!peerRef.current) return;
    for (const candidate of pendingIceRef.current) {
      try {
        await peerRef.current.addIceCandidate(candidate);
      } catch {
        // Ignore stale candidates if the peer is already resetting.
      }
    }
    pendingIceRef.current = [];
  };

  const createPeerConnection = async () => {
    const peer = new RTCPeerConnection(RTC_CONFIGURATION);
    peerRef.current = peer;
    remoteStreamRef.current = new MediaStream();

    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = remoteStreamRef.current;
    }

    peer.onicecandidate = (event) => {
      if (event.candidate) {
        sendEvent({ type: "webrtc_ice_candidate", candidate: event.candidate });
      }
    };

    peer.ontrack = (event) => {
      event.streams[0].getTracks().forEach((track) => {
        remoteStreamRef.current.addTrack(track);
      });
    };

    peer.onconnectionstatechange = () => {
      if (peer.connectionState === "connected") {
        clearNoAnswerTimer();
        setCallState("connected");
        setStatusText("Call connected.");
      } else if (["disconnected", "failed", "closed"].includes(peer.connectionState)) {
        cleanupCall("ended", "Call ended.");
      }
    };

    const stream = await ensureLocalStream();
    stream.getTracks().forEach((track) => peer.addTrack(track, stream));
    return peer;
  };

  const startCall = async () => {
    if (!sendEvent) return;
    try {
      const peer = await createPeerConnection();
      const offer = await peer.createOffer();
      await peer.setLocalDescription(offer);
      sendEvent({ type: "webrtc_offer", offer });
      setCallState("calling");
      setStatusText("Calling the other participant...");
      startNoAnswerTimer();
    } catch {
      cleanupCall("error", "Could not access camera and microphone.");
    }
  };

  const answerCall = async () => {
    if (!pendingOfferRef.current || !sendEvent) return;
    try {
      const peer = await createPeerConnection();
      await peer.setRemoteDescription(pendingOfferRef.current);
      await flushPendingIce();
      const answer = await peer.createAnswer();
      await peer.setLocalDescription(answer);
      sendEvent({ type: "webrtc_answer", answer });
      pendingOfferRef.current = null;
      setCallState("connecting");
      setStatusText("Joining the call...");
    } catch {
      cleanupCall("error", "Could not answer the incoming call.");
    }
  };

  const endCall = () => {
    sendEvent?.({ type: "call_end" });
    cleanupCall("ended", "Call ended.");
  };

  useEffect(() => {
    return () => cleanupCall();
  }, []);

  useEffect(() => {
    if (!socketEvent || socketEvent.case_id !== caseId) return;

    if (socketEvent.type === "webrtc_offer" && callState !== "connected") {
      pendingOfferRef.current = socketEvent.offer;
      setCallState("incoming");
      setStatusText("Incoming call. Answer to join.");
      return;
    }

    if (socketEvent.type === "webrtc_answer" && peerRef.current) {
      clearNoAnswerTimer();
      peerRef.current.setRemoteDescription(socketEvent.answer).then(async () => {
        await flushPendingIce();
        setCallState("connecting");
        setStatusText("Connecting call...");
      }).catch(() => {
        cleanupCall("error", "Could not complete the call handshake.");
      });
      return;
    }

    if (socketEvent.type === "webrtc_ice_candidate") {
      const candidate = socketEvent.candidate;
      if (!candidate) return;

      if (peerRef.current?.remoteDescription) {
        peerRef.current.addIceCandidate(candidate).catch(() => {
          // Ignore candidates that arrive during teardown.
        });
      } else {
        pendingIceRef.current.push(candidate);
      }
      return;
    }

    if (socketEvent.type === "call_end" || socketEvent.type === "call_declined") {
      cleanupCall("ended", socketEvent.type === "call_declined" ? "The other participant declined the call." : "The other participant ended the call.");
    }
  }, [callState, caseId, socketEvent]);

  const isIdle = callState === "idle" || callState === "ended" || callState === "no_answer";

  return (
    <div className="bg-white rounded-2xl border border-[#E2E6F0] shadow-sm p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <p className="text-[15px] font-bold text-[#1A1E2E]">Case Call</p>
          <p className="text-[12px] text-[#737A8F]">{caseLabel || `Case #${caseId}`}</p>
        </div>
        <span className="text-[11px] uppercase tracking-wide text-[#1A78F2] bg-[#EBF3FF] border border-[#BDD6FF] rounded-full px-3 py-1">
          {socketStatus}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="rounded-2xl overflow-hidden border border-[#E2E6F0] bg-[#09111F] aspect-video">
          <video ref={remoteVideoRef} autoPlay playsInline className="h-full w-full object-cover" />
        </div>
        <div className="rounded-2xl overflow-hidden border border-[#E2E6F0] bg-[#09111F] aspect-video">
          <video ref={localVideoRef} autoPlay muted playsInline className="h-full w-full object-cover" />
        </div>
      </div>

      <p className="text-[13px] text-[#4A5068] mb-4">{statusText}</p>

      <div className="flex gap-3">
        {isIdle && (
          <button onClick={startCall} className="rounded-xl bg-[#1A78F2] px-4 py-2 text-[13px] font-semibold text-white">
            Start Call
          </button>
        )}
        {callState === "incoming" && (
          <button onClick={answerCall} className="rounded-xl bg-[#17B86B] px-4 py-2 text-[13px] font-semibold text-white">
            Answer Call
          </button>
        )}
        {["calling", "connecting", "connected", "incoming"].includes(callState) && (
          <button onClick={endCall} className="rounded-xl border border-[#EE3B3B] px-4 py-2 text-[13px] font-semibold text-[#EE3B3B]">
            End Call
          </button>
        )}
      </div>
    </div>
  );
}
