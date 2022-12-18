import { getReaderBasePath } from "@/api/v3/common";
import { useCommonStore } from "@/stores/common";

import { HTTP } from "./base";

const getParams = () => {
  return { ts: useCommonStore().timestamp };
};

const getReaderInfo = (pk) => {
  const params = getParams();
  return HTTP.get(`c/${pk}`, { params });
};

const getReaderSettings = () => {
  const params = getParams();
  return HTTP.get(`c/settings`, { params });
};

const setReaderSettings = (data) => {
  return HTTP.put(`c/settings`, data);
};

export const getDownloadURL = (pk) => {
  const BASE_URL = getReaderBasePath(pk);
  const timestamp = useCommonStore().timestamp;
  return `${BASE_URL}/download.cbz?ts=${timestamp}`;
};

export const getComicPageSource = ({ pk, page }) => {
  const BASE_URL = getReaderBasePath(pk);
  const timestamp = useCommonStore().timestamp;
  return `${BASE_URL}/${page}/page.jpg?ts=${timestamp}`;
};

export default {
  getReaderBasePath,
  getReaderInfo,
  getReaderSettings,
  setReaderSettings,
};
