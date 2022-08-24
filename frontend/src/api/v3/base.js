import axios from "axios";
const CONFIG = {
  baseURL: window.CODEX.API_V3_PATH,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFTOKEN",
};
export const HTTP = axios.create(CONFIG);
