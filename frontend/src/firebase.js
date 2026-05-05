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

// getMessaging() can throw if FCM is unsupported (no service worker, missing
// env vars, or non-HTTPS context). Keep it lazy so it never crashes app init.
export let messaging = null;
isSupported()
  .then((supported) => {
    if (supported) {
      messaging = getMessaging(app);
    }
  })
  .catch((err) => {
    console.warn("Firebase Messaging not available:", err.message);
  });
