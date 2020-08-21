if (window.fetch) {
  fetch(location, { method: "HEAD" })
    .then((request) => {
      request.headers.forEach((key, value) => {
        if (["Daphne-Root-Path"].includes(key)) {
          /* global __webpack_public_path__:writable */
          __webpack_public_path__ = __webpack_public_path__ + value;
        }
      });
      return undefined;
    })
    .catch((error) => {
      console.error(error);
    });
}
