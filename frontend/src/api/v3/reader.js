import { getReaderBasePath, getTSParams } from "@/api/v3/common";

import { HTTP } from "./base";

const getReaderInfo = (pk) => {
  const params = getTSParams();
  return HTTP.get(`c/${pk}`, { params });
};

const getReaderSettings = () => {
  const params = getTSParams();
  return HTTP.get(`c/settings`, { params });
};

const setReaderSettings = (data) => {
  return HTTP.put(`c/settings`, data);
};

export const getDownloadURL = (pk) => {
  const BASE_URL = getReaderBasePath(pk);
  const timestamp = getTSParams().ts;
  return `${BASE_URL}/download.cbz?ts=${timestamp}`;
};

export const getComicPageSource = ({ pk, page }) => {
  const BASE_URL = getReaderBasePath(pk);
  const timestamp = getTSParams().ts;
  return `${BASE_URL}/${page}/page.jpg?ts=${timestamp}`;
};

export default {
  getReaderBasePath,
  getReaderInfo,
  getReaderSettings,
  setReaderSettings,
};
