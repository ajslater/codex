// Initialize the service worker
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register("{% url 'pwa:serviceworker' %}", {
    scope: "{% url 'app' %}"
  }).then(function (registration) {
    // Registration was successful
    console.debug('codex-pwa: ServiceWorker registration successful with scope: ', registration.scope);
  }, function (err) {
    // registration failed :(
    console.warn('codex-pwa: ServiceWorker registration failed: ', err);
  });
}
