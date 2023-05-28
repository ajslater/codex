import { getReaderBasePath, getReaderPath, getTSParams } from "@/api/v3/common";

import { HTTP } from "./base";

const getReaderInfo = (params) => {
  const pk = params.pk;
  const tsParams = getTSParams();
  params = { ...params, ...tsParams };
  delete params.pk;
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
  const READER_PATH = getReaderPath(pk);
  const timestamp = getTSParams().ts;
  return `${READER_PATH}/download/comic-${pk}.cbz?ts=${timestamp}`;
};

export const getDownloadPageURL = ({ pk, page }) => {
  const READER_PATH = getReaderPath(pk);
  const timestamp = getTSParams().ts;
  return `${READER_PATH}/${page}/page.jpg?ts=${timestamp}`;
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
