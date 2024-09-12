// {% load static %}
const CACHE_PREFIX = "codex-pwa-v";
const STATIC_CACHE_NAME = CACHE_PREFIX + new Date().getSeconds();
const OFFLINE_PATH = "{% static 'pwa/offline.html' %}";
const FILES_TO_CACHE = [
  OFFLINE_PATH,
  "{% static 'img/logo-32.webp' %}",
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
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => cacheName.startsWith(CACHE_PREFIX))
          .filter((cacheName) => cacheName !== STATIC_CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName)),
      );
    }),
  );
});
// Serve from Cache
self.addEventListener("fetch", (event) => {
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
