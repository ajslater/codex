import xior, { merge } from "xior";

/*
 * Codex may be mounted under a URL path prefix (server.url_path_prefix),
 * e.g. "/codex" behind a reverse proxy. window.CODEX.APP_PATH carries that
 * prefix as an absolute path with a trailing slash ("/" at the server root),
 * so every API request, WebSocket, cover, and download resolves under the
 * same mount as the SPA instead of the server root. Hardcoding "/api/v4/"
 * here sent the whole v4 client to the root, which 404s under a subpath and
 * breaks the websocket route.
 */
export const APP_BASE = globalThis.CODEX?.APP_PATH || "/";
export const V4_BASE = `${APP_BASE}api/v4/`;

const CONFIG = {
  baseURL: V4_BASE,
  withCredentials: true,
};

export const HTTP = xior.create(CONFIG);

const COOKIE_NAME = "csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const CSRF_COOKIE_REGEX = RegExp("(?:^|;)\\s*" + COOKIE_NAME + "=([^;]*)");

let _cachedCookieSnapshot = "";
let _cachedToken = "";

function readCSRFToken() {
  const cookie = document.cookie;
  if (cookie === _cachedCookieSnapshot) return _cachedToken;
  _cachedCookieSnapshot = cookie;
  const match = cookie.match(CSRF_COOKIE_REGEX);
  _cachedToken = match ? match[1] : "";
  return _cachedToken;
}

HTTP.interceptors.request.use((config) => {
  const token = readCSRFToken();
  if (!token) return config;
  return merge(config, {
    headers: {
      [CSRF_HEADER]: token,
    },
  });
});

export class APIError extends Error {
  constructor(envelopeError, status) {
    super(envelopeError?.detail || envelopeError?.title || "API error");
    this.name = "APIError";
    this.status = status;
    this.envelopeError = envelopeError;
  }
}

export const HTTP_REDIRECT_CODES = Object.freeze(
  new Set([301, 302, 303, 307, 308]),
);

/*
 * Reject an enveloped error response.
 *
 * Two shapes arrive here, and they must not be treated alike:
 *
 *   - An error carries its content in ``errors`` and a null ``data``
 *     (see codex/views/envelope.py). The first error becomes an
 *     APIError. ``data`` is deliberately left wrapped, because
 *     unwrapping it would hand every consumer of
 *     ``error.response.data`` -- ``fieldErrorMap`` in stores/common.js,
 *     the identifier-url dialog in edit-panel.vue -- a null.
 *   - Codex's redirect is a 303 with the target route in ``data`` and
 *     no ``Location`` header, so fetch cannot follow it and it lands
 *     here instead. Unwrap that one the way the success interceptor
 *     unwraps a 200, or ``handlePageError`` reads ``settings`` and
 *     ``route`` off the envelope itself, finds neither, and leaves the
 *     page silently stale.
 */
export const rejectEnvelopeError = (error) => {
  const body = error?.response?.data;
  if (body && typeof body === "object") {
    const first = Array.isArray(body.errors) ? body.errors[0] : undefined;
    if (first) {
      return Promise.reject(new APIError(first, error.response.status));
    }
    if (
      HTTP_REDIRECT_CODES.has(error.response.status) &&
      body.data &&
      typeof body.data === "object"
    ) {
      error.response.data = body.data;
      error.response.meta = body.meta || {};
    }
  }
  return Promise.reject(error);
};

/*
 * Unwrap the v4 envelope so callers can read ``response.data``
 * directly. ``meta`` is preserved as ``response.meta`` for the rare
 * caller that needs pagination cursors / mtime hints.
 */
HTTP.interceptors.response.use((response) => {
  const body = response.data;
  if (body && typeof body === "object" && "data" in body) {
    response.data = body.data;
    response.meta = body.meta || {};
    response.envelopeErrors = body.errors || [];
  }
  return response;
}, rejectEnvelopeError);
