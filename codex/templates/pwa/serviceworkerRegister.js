// Initialize the service worker
var rootPath = "{{ script_prefix }}";
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register(rootPath + 'serviceworker.js', {
    scope: rootPath
  }).then(function (registration) {
    // Registration was successful
    {% if DEBUG %}
    console.log('codex-pwa: ServiceWorker registration successful with scope: ', registration.scope);
    {% endif %}
  }, function (err) {
    // registration failed :(
    console.warn('codex-pwa: ServiceWorker registration failed: ', err);
  });
}
