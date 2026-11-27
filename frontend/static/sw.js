/* FarmBridge service worker.
   Caches only static files (css, js, fonts, images) and one offline page.
   Pages, login sessions, carts and orders are never stored: they always come from the server. */
const VERSION = "fb-v2";
const STATIC_CACHE = "fb-static-" + VERSION;
const OFFLINE_URL = "/offline";
const OFFLINE_CACHE = "fb-offline-" + VERSION;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(OFFLINE_CACHE).then((c) => c.add(new Request(OFFLINE_URL, { cache: "reload" }))).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith("fb-") && k !== STATIC_CACHE && k !== OFFLINE_CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/admin")) return; // admin panel stays a normal website

  // Pages: always the network. If the phone is offline, show the offline page.
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match(OFFLINE_URL, { cacheName: OFFLINE_CACHE })));
    return;
  }

  // Static files only (their URLs carry ?v=<time>, so a new version is a new entry).
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(STATIC_CACHE).then((cache) =>
        cache.match(req).then((hit) => hit || fetch(req).then((res) => {
          if (res.ok) cache.put(req, res.clone());
          return res;
        }))
      )
    );
  }
  // everything else (API-backed pages, /media, forms) goes straight to the network
});
