// Initialize the service worker
var ROOT_PATH = "{{ script_prefix }}";
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register(ROOT_PATH + 'serviceworker.js', {
    scope: ROOT_PATH
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
