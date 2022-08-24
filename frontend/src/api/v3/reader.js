import { HTTP } from "./base";

export const getReaderBasePath = (pk) => {
  return `${window.CODEX.API_V3_PATH}c/${pk}`;
};

const getReaderInfo = (pk, timestamp) => {
  return HTTP.get(`c/${pk}?ts=${timestamp}`);
};

const getComicSettings = (pk, timestamp) => {
  return HTTP.get(`c/${pk}/settings?ts=${timestamp}`);
};

const getReaderSettings = () => {
  return HTTP.get(`c/settings`);
};

const setReaderSettings = (data) => {
  return HTTP.put(`c/settings`, data);
};

export const getDownloadURL = (pk, timestamp) => {
  const BASE_URL = getReaderBasePath(pk);
  return `${BASE_URL}/download.cbz?ts=${timestamp}`;
};

export const getComicPageSource = ({ pk, page }, timestamp) => {
  const BASE_URL = getReaderBasePath(pk);
  return `${BASE_URL}/${page}/page.jpg?ts=${timestamp}`;
};

export default {
  getComicSettings,
  getReaderBasePath,
  getReaderInfo,
  getReaderSettings,
  setReaderSettings,
};
