import axios from "axios";
export const ROOT_PATH = `${window.rootPath}`;
export const API_PREFIX = `${ROOT_PATH}api/v1`;
const CONFIG = {
  baseURL: API_PREFIX,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFTOKEN",
};
export const HTTP = axios.create(CONFIG);

export const ajax = (method, url, data, qparams) => {
  return HTTP({ method, url, data, params: qparams });
};
