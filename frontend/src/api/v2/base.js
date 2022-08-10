import axios from "axios";
export const ROOT_PATH = window.rootPath;
const VERSION = 2;
export const API_PREFIX = `${ROOT_PATH}api/v${VERSION}`;
const CONFIG = {
  baseURL: API_PREFIX,
  withCredentials: true,
  xsrfCookieName: "csrftoken",
  xsrfHeaderName: "X-CSRFTOKEN",
};
export const HTTP = axios.create(CONFIG);

// TODO just return the  HTTP instance let api use get() post() and url and data
export const ajax = (method, url, data, qparams) => {
  return HTTP({ method, url, data, params: qparams });
};
