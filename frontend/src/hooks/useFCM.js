/**
 * useFCM — Firebase Cloud Messaging hook for push notification registration.
 *
 * On mount:
 *   1. Waits for Firebase Messaging to initialize
 *   2. Requests notification permission
 *   3. Gets the FCM token from the browser
 *   4. Sends it to the backend via POST /api/users/fcm-token
 *   5. Subscribes to foreground messages and returns them via `lastPush`
 *
 * Usage:
 *   const { lastPush, fcmStatus } = useFCM();
 *   // lastPush changes every time a foreground FCM message arrives
 *   // fcmStatus: "idle" | "requesting" | "ready" | "denied" | "unsupported" | "error"
 */
import { useEffect, useRef, useState } from "react";
import { getToken, onMessage } from "firebase/messaging";
import { messagingReady } from "../firebase";
import api from "../api/axios";

export default function useFCM() {
  const [lastPush, setLastPush] = useState(null);
  const [fcmStatus, setFcmStatus] = useState("idle");
  const registeredRef = useRef(false);

  useEffect(() => {
    if (registeredRef.current) return;

    let unsubscribe;
    let cancelled = false;

    async function init() {
      setFcmStatus("requesting");

      try {
        // Step 0: Wait for messaging to be ready
        const msgInstance = await messagingReady;

        if (cancelled) return;

        if (!msgInstance) {
          setFcmStatus("unsupported");
          return;
        }

        // Step 1: Ask for notification permission
        const permission = await Notification.requestPermission();
        if (cancelled) return;

        if (permission !== "granted") {
          setFcmStatus("denied");
          return;
        }

        // Step 2: Get the FCM token
        const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY;
        const token = await getToken(msgInstance, { vapidKey });
        if (cancelled) return;

        if (!token) {
          setFcmStatus("error");
          return;
        }

        // Step 3: Register token with the backend
        try {
          await api.post("/api/users/fcm-token", { token });
        } catch (err) {
          // Non-critical: backend might be unreachable, but we still listen
          console.warn("Failed to register FCM token with backend:", err);
        }

        if (cancelled) return;

        registeredRef.current = true;
        setFcmStatus("ready");

        // Step 4: Listen for foreground messages
        unsubscribe = onMessage(msgInstance, (payload) => {
          console.log("[useFCM] Foreground push received:", payload);
          setLastPush({
            title: payload.notification?.title,
            body: payload.notification?.body,
            data: payload.data || {},
            receivedAt: Date.now(),
          });
        });
      } catch (err) {
        console.error("[useFCM] Initialization failed:", err);
        if (!cancelled) setFcmStatus("error");
      }
    }

    init();

    return () => {
      cancelled = true;
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, []);

  return { lastPush, fcmStatus };
}
