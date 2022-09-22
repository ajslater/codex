// {% load static %}
var CACHE_PREFIX = "codex-pwa-v"
var STATIC_CACHE_NAME = CACHE_PREFIX + new Date().getSeconds();
var OFFLINE_PATH = "{% static 'pwa/offline.html' %}";
var FILES_TO_CACHE = [
  OFFLINE_PATH,
  "{% static 'img/logo-maskable-180.webp' %}",
  "{% static 'img/logo.svg' %}",
  "{% static 'img/logo-32.webp' %}",
  "{% static 'img/logo-maskable.svg' %}",
];
// Cache on install
self.addEventListener("install", (event) => {
  this.skipWaiting();
  event.waitUntil(
    // eslint-disable-next-line security/detect-non-literal-fs-filename
    caches.open(STATIC_CACHE_NAME).then((cache) => {
      return cache.addAll(FILES_TO_CACHE);
    })
  );
});
// Clear cache on activate
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => cacheName.startsWith(CACHE_PREFIX))
          .filter((cacheName) => cacheName !== STATIC_CACHE_NAME)
          .map((cacheName) => caches.delete(cacheName))
      );
    })
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
      })
  );
});
