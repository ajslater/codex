import xior, { merge } from "xior";

const BASE_URL = "/api/v4/";

const CONFIG = {
  baseURL: BASE_URL,
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
