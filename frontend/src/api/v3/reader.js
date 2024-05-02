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
  return HTTP.get(`c/settings`);
};

const setReaderSettings = (data) => {
  return HTTP.put(`c/settings`, data);
};

export const getDownloadURL = ({ pk, mtime }) => {
  const READER_PATH = getReaderPath(pk);
  return `${READER_PATH}/download/comic-${pk}.cbz?mtime=${mtime}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) => {
  const READER_PATH = getReaderPath(pk);
  return `${READER_PATH}/${page}/page.jpg?mtime=${mtime}`;
};

export const getComicPageSource = ({ pk, page, mtime }) => {
  const BASE_URL = getReaderBasePath(pk);
  return `${BASE_URL}/${page}/page.jpg?mtime=${mtime}`;
};

export const getPdfBookSource = ({ pk, mtime }) => {
  return `/c/${pk}/book.pdf?mtime=${mtime}`;
};

export default {
  getPdfBookSource,
  getReaderBasePath,
  getReaderInfo,
  getReaderSettings,
  setReaderSettings,
};
