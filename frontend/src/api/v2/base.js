import axios from "axios";
const CONFIG = {
  baseURL: window.CODEX.API_V2_PATH,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFTOKEN",
};
export const HTTP = axios.create(CONFIG);

// TODO just return the  HTTP instance let api use get() post() and url and data
export const ajax = (method, url, data, qparams) => {
  return HTTP({ method, url, data, params: qparams });
};
