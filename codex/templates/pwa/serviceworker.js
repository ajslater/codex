// {% load static %}
const CACHE_PREFIX = "codex-pwa-v";
const STATIC_CACHE_NAME = CACHE_PREFIX + new Date().getSeconds();
const OFFLINE_PATH = "{% static 'pwa/offline.html' %}";
const FILES_TO_CACHE = [
  OFFLINE_PATH,
  "{% static 'img/logo-maskable-180.webp' %}",
  "{% static 'img/logo-maskable.svg' %}",
  "{% static 'img/logo.svg' %}",
];
// Cache offline page on install
self.addEventListener("install", (event) => {
  this.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      return cache.addAll(FILES_TO_CACHE);
    }),
  );
});
// Clear old caches on activate
self.addEventListener("activate", (event) => {
  event.waitUntil(
    Promise.all([
      // Pair with skipWaiting() so the new SW takes control of
      // already-open pages immediately. Without this, replacing a
      // stale SW (e.g. one with a stale CSP) would need a second
      // reload to take effect.
      self.clients.claim(),
      caches.keys().then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((cacheName) => cacheName.startsWith(CACHE_PREFIX))
            .filter((cacheName) => cacheName !== STATIC_CACHE_NAME)
            .map((cacheName) => caches.delete(cacheName)),
        );
      }),
    ]),
  );
});
// Serve from Cache
self.addEventListener("fetch", (event) => {
  // Pass through non-GET and cross-origin requests so the browser
  // handles them under the page's CSP rather than the SW's snapshot
  // taken at install time. Vite HMR talks to a separate origin
  // (5173) and would otherwise be blocked by a stale SW CSP that
  // pre-dates the dev-only overlay.
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) {
    return;
  }
  event.respondWith(
    caches
      .match(event.request)
      .then((response) => {
        return response || fetch(event.request);
      })
      .catch(() => {
        return caches.match(OFFLINE_PATH);
      }),
  );
});
