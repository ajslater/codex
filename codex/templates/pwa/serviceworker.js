{% load static %}
var staticCacheName = "codex-pwa-v" + new Date().getTime();
var filesToCache = [
  "/offline",
  "{% static 'img/apple-touch-icon.webp' %}",
  "{% static 'img/favicon-32.webp' %}",
  "{% static 'img/favicon-128.webp' %}",
  "{% static 'img/favicon-180.webp' %}",
  "{% static 'img/favicon-192.webp' %}",
  "{% static 'img/favicon-512.webp' %}",
  "{% static 'img/favicon.ico' %}",
  "{% static 'img/favicon.svg' %}",
];
// Cache on install
self.addEventListener("install", (event) => {
  this.skipWaiting();
  event.waitUntil(
    caches.open(staticCacheName).then((cache) => {
      return cache.addAll(filesToCache);
    })
  );
});
// Clear cache on activate
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => cacheName.startsWith("codex-pwa-"))
          .filter((cacheName) => cacheName !== staticCacheName)
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
        return caches.match("offline");
      })
  );
});
