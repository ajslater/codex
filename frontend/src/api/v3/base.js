import xior, { merge } from "xior";

import { useCommonStore } from "@/stores/common";
const CONFIG = {
  baseURL: globalThis.CODEX.API_V3_PATH,
  withCredentials: true,
};
export const HTTP = xior.create(CONFIG);

// Default Django CSRF token
const COOKIE_NAME = "csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const CSRF_COOKIE_REGEX = RegExp("(?:^|;)\\s*" + COOKIE_NAME + "=([^;]*)");

// Cookie-string cache: we re-run the regex only when
// ``document.cookie`` actually changes. The previous code matched
// the regex against the full cookie string on every single API
// request — a cheap operation per call, but multiplied across the
// many requests a single page navigation fires (browser page +
// available filters + per-field choices + mtime poll), it added up
// to noticeable redundant work. Caching the token string and the
// cookie snapshot it was extracted from lets us hit a constant-time
// string equality check in the common case while still picking up
// rotated tokens automatically (the cookie string changes whenever
// Django rotates the CSRF cookie).
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

function invalidateCSRFCache() {
  _cachedCookieSnapshot = "";
  _cachedToken = "";
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

/*
 * When versions of django change users are sometimes caught with CSRF errors
 * And only logging out fixes it.
 */
HTTP.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Intercept all errors
    if (
      error.response?.status === 403 &&
      typeof error.response.data === "string" &&
      error.response.data.includes("CSRF")
    ) {
      /*
       * CSRF failure — drop the cached token so the next request
       * forces a fresh cookie read, then delete the sessionid
       * cookie so the user is logged out cleanly. Surface a
       * snackbar so the user knows why the page just stopped
       * working; without this every subsequent API call returns
       * 401 silently and the UI appears broken.
       *
       * The static ``useCommonStore`` import forms a module cycle
       * (``stores/common`` → ``api/v3/common`` → this file), but
       * the handler only runs at request time — long after every
       * module has finished evaluating — so the ESM live binding
       * resolves cleanly.
       */
      invalidateCSRFCache();
      await cookieStore.delete("sessionid");
      console.error("CSRF response error. Deleted login cookie.");
      try {
        useCommonStore().setSessionError(
          "Your session expired. Please reload the page.",
        );
      } catch (notifyError) {
        console.error("Failed to surface CSRF error toast:", notifyError);
      }
    }
    return Promise.reject(error);
  },
);
