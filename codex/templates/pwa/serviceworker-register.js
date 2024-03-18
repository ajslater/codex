// Initialize the service worker
if ("serviceWorker" in navigator) {
  navigator.serviceWorker
    .register("{% url 'pwa:serviceworker' %}", {
      scope: "{% url 'app:start' %}",
    })
    .then(function (registration) {
      // Registration was successful
      console.debug(
        "codex-pwa: ServiceWorker registration successful with scope:",
        registration.scope,
      );
      return true;
      // eslint-disable-next-line unicorn/prefer-top-level-await
    })
    .catch(function (error) {
      // registration failed :(
      console.warn("codex-pwa: ServiceWorker registration failed:", error);
    });
}
