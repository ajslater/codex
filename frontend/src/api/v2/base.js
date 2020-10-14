import axios from "axios";
export const ROOT_PATH = `${window.rootPath}`;
export const ADMIN_URL = `${ROOT_PATH}admin/`;
const VERSION = 2;
export const API_PREFIX = `${ROOT_PATH}api/v${VERSION}`;
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
