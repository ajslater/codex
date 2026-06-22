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

/*
 * Unwrap the v4 envelope so callers can read ``response.data``
 * directly. ``meta`` is preserved as ``response.meta`` for the rare
 * caller that needs pagination cursors / mtime hints.
 */
HTTP.interceptors.response.use(
  (response) => {
    const body = response.data;
    if (body && typeof body === "object" && "data" in body) {
      response.data = body.data;
      response.meta = body.meta || {};
      response.envelopeErrors = body.errors || [];
    }
    return response;
  },
  (error) => {
    const body = error?.response?.data;
    if (body && typeof body === "object" && Array.isArray(body.errors)) {
      const first = body.errors[0];
      if (first) {
        return Promise.reject(new APIError(first, error.response.status));
      }
    }
    return Promise.reject(error);
  },
);
