const CACHE_NAME = "cspm-quick-expense-__LPN_APP_VERSION__";
const ASSETS = ["/", "/index.html", "/manifest.json", "/icon.svg", "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png", "/favicon.ico"];

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("push", (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json() || {};
    } catch (_) {
      data = { title: "Quick Expense", body: event.data.text() };
    }
  }
  const title = data.title || "Quick Expense";
  const options = {
    body: data.body || "A new Quick Expense update is available.",
    icon: data.icon || "/icon-192.png",
    badge: data.badge || "/icon-192.png",
    data: data.data || data,
    tag: data.tag || "lpn-qe-push",
    renotify: true,
  };

  event.waitUntil(
    (async () => {
      try {
        if (data.badge && self.navigator && typeof self.navigator.setAppBadge === "function") {
          await self.navigator.setAppBadge(Number(data.badge) || 1);
        }
      } catch (_) {}

      if (data.type === "APP_UPDATE" || data.type === "LPN_APP_UPDATE") {
        try {
          await self.registration.update();
        } catch (_) {}
      }

      try {
        const clientList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
        for (const client of clientList) {
          if (data.type === "APP_UPDATE") {
            client.postMessage({ type: "LPN_REMOTE_VERSION_PUSH", version: data.version || "" });
          } else {
            client.postMessage({ type: "QE_PUSH_RECEIVED", payload: data });
          }
        }
      } catch (_) {}

      await self.registration.showNotification(title, options);
    })()
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const notifData = (event.notification && event.notification.data) || {};
  const isUpdate = notifData.type === "APP_UPDATE" || notifData.type === "LPN_APP_UPDATE" || event.notification.tag === "lpn-qe-update-available";
  const targetUrl = notifData.url || "/?source=pwa";

  event.waitUntil(
    (async () => {
      try {
        if (self.navigator && typeof self.navigator.clearAppBadge === "function") {
          await self.navigator.clearAppBadge();
        }
      } catch (_) {}

      const clientList = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of clientList) {
        if ("focus" in client) {
          await client.focus();
          if (isUpdate) {
            client.postMessage({ type: "LPN_APPLY_UPDATE_NOW" });
          } else {
            client.postMessage({ type: "QE_PUSH_CLICKED", payload: notifData });
          }
          return;
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(targetUrl);
      }
    })()
  );
});

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    (async () => {
      try {
        const keyRes = await fetch("/api/push/vapid-public-key", { cache: "no-store" });
        const keyData = await keyRes.json();
        if (!keyData || !keyData.publicKey) return;
        const newSub = await self.registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(keyData.publicKey),
        });
        await fetch("/api/push/subscribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: "cory", subscription: newSub.toJSON() }),
        });
      } catch (_) {}
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname === "/sw.js") {
    return;
  }
  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cachedResponse = await cache.match(event.request) || await cache.match("/");
      const fetchPromise = fetch(event.request)
        .then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        })
        .catch(() => cachedResponse);
      return cachedResponse || fetchPromise;
    })
  );
});
