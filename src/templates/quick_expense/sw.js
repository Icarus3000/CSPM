const CACHE_NAME = "cspm-quick-expense-v10";
const ASSETS = ["/", "/index.html", "/manifest.json", "/icon.svg"];

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
      const windowClients = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const client of windowClients) {
        try {
          await client.navigate(client.url);
        } catch (e) {}
      }
    })()
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/") || url.pathname === "/sw.js") {
    return;
  }
  // Network-first with fast 1500ms timeout fallback to cache so phones/Chromebooks
  // always get the latest UI immediately when connected, and still work offline!
  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cachedResponse = await cache.match(event.request) || await cache.match("/");
      try {
        const res = await new Promise((resolve, reject) => {
          const timer = setTimeout(() => reject(new Error("timeout")), 1500);
          fetch(event.request)
            .then((networkRes) => {
              clearTimeout(timer);
              if (networkRes && networkRes.ok) {
                cache.put(event.request, networkRes.clone()).catch(() => {});
              }
              resolve(networkRes);
            })
            .catch((err) => {
              clearTimeout(timer);
              reject(err);
            });
        });
        if (res && res.ok) {
          return res;
        }
      } catch (e) {}
      return cachedResponse || new Response("Offline", { status: 503 });
    })
  );
});
