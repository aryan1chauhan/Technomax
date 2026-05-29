import { initializeApp } from "firebase/app";
import { getMessaging, isSupported } from "firebase/messaging";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

export const app = initializeApp(firebaseConfig);

// Eagerly initialized — resolves to the messaging instance or null.
// Consumers that need `messaging` should await this promise to avoid the
// race condition where `messaging` is still null when the hook runs.
export let messaging = null;

export const messagingReady = isSupported()
  .then((supported) => {
    if (supported) {
      messaging = getMessaging(app);
    }
    return messaging;
  })
  .catch((err) => {
    console.warn("Firebase Messaging not available:", err.message);
    return null;
  });
