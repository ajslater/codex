import axios from "axios";
export const BASE_URL = "/api";
const CONFIG = {
  baseURL: BASE_URL,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFTOKEN",
};
export const HTTP = axios.create(CONFIG);

export const ajax = (method, url, data, qparams) => {
  return HTTP({ method, url, data, params: qparams });
};
