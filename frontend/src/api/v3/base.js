import xior, { merge } from "xior";
const CONFIG = {
  baseURL: globalThis.CODEX.API_V3_PATH,
  withCredentials: true,
};
export const HTTP = xior.create(CONFIG);

// Default Django CSRF token
const COOKIE_NAME = "csrftoken";
const CSRF_HEADER = "X-CSRFToken";
const CSRF_COOKIE_REGEX = RegExp("(?:^|;)\\s*" + COOKIE_NAME + "=([^;]*)");

HTTP.interceptors.request.use((config) => {
  const match = document.cookie.match(CSRF_COOKIE_REGEX);
  const token = match ? match[1] : "";
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
      // CSRF failure — delete the sessionid cookie
      await cookieStore.delete("sessionid");
      console.error("CSRF response error. Deleted login cookie.");
    }
    return Promise.reject(error);
  },
);
