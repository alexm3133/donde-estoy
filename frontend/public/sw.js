/*
 * Minimal service worker. Its only job is to let the viewer page show system
 * notifications on Android (where `new Notification()` is not allowed and
 * `registration.showNotification()` must be used). It caches nothing.
 */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

// Tapping a notification brings the viewer tab back to the front.
self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const target = event.notification.data && event.notification.data.url;
      const open = clients.find((client) => !target || client.url === target) || clients[0];
      if (open) return open.focus();
      if (target) return self.clients.openWindow(target);
    }),
  );
});
