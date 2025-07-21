import axios from "axios";
const CONFIG = {
  baseURL: globalThis.CODEX.API_V3_PATH,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFTOKEN",
};
export const HTTP = axios.create(CONFIG);

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
