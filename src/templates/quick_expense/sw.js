const CACHE_NAME = "cspm-quick-expense-__LPN_APP_VERSION__";
const ASSETS = ["/", "/index.html", "/manifest.json", "/icon.svg", "/icon-192.png", "/icon-512.png", "/icon-maskable-512.png", "/apple-touch-icon.png", "/favicon.ico"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)));
      await self.clients.claim();
    })()
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") self.skipWaiting();
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if ("focus" in client) {
          client.focus();
          client.postMessage({ type: "LPN_APPLY_UPDATE_NOW" });
          return;
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow("/?source=pwa");
      }
    })
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname === "/sw.js") {
    return;
  }
  // Network-first with 6000ms timeout fallback to cache; never return synthetic "Offline" if network is still in-flight
  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cachedResponse = await cache.match(event.request) || await cache.match("/");
      try {
        const netPromise = fetch(event.request).then((networkRes) => {
          if (networkRes && networkRes.ok) {
            cache.put(event.request, networkRes.clone()).catch(() => {});
          }
          return networkRes;
        });
        if (cachedResponse) {
          const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error("timeout")), 5000)
          );
          const res = await Promise.race([netPromise, timeoutPromise]);
          if (res && res.ok) return res;
        } else {
          const res = await netPromise;
          if (res && res.ok) return res;
        }
      } catch (e) {}
      if (cachedResponse) return cachedResponse;
      return fetch(event.request);
    })
  );
});
