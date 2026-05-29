// firebase-messaging-sw.js — Background push notifications for MediRoute
/* eslint-env serviceworker */
/* global firebase */
importScripts("https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/10.8.0/firebase-messaging-compat.js");

firebase.initializeApp({
  apiKey: "AIzaSyATmuOcs4Xajvsi-bQRJUgRRiCj46Ovxp0",
  authDomain: "mediroute-7b616.firebaseapp.com",
  projectId: "mediroute-7b616",
  storageBucket: "mediroute-7b616.appspot.com",
  messagingSenderId: "1066439121745",
  appId: "1:1066439121745:web:e3f08cbd3dcfedd6249170",
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  console.log("[firebase-messaging-sw.js] Background message:", payload);

  const title = payload.notification?.title || "MediRoute Alert";
  const options = {
    body: payload.notification?.body || "New emergency case dispatched.",
    icon: "/favicon.svg",
    badge: "/favicon.svg",
    data: payload.data || {},
    tag: `mediroute-case-${payload.data?.case_id || "unknown"}`,
    requireInteraction: true, // Keep notification visible until dismissed
  };

  self.registration.showNotification(title, options);
});

// Navigate to hospital dashboard when notification is clicked
self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const caseId = event.notification.data?.case_id;
  const url = caseId
    ? `/hospital/dashboard?highlight=${caseId}`
    : "/hospital/dashboard";

  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((clientList) => {
        // Focus existing tab if open
        for (const client of clientList) {
          if (client.url.includes("/hospital") && "focus" in client) {
            return client.focus();
          }
        }
        // Otherwise open a new tab
        if (self.clients.openWindow) {
          return self.clients.openWindow(url);
        }
      })
  );
});
