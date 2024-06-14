import {
  getReaderBasePath,
  getReaderPath,
  serializeParams,
} from "@/api/v3/common";

import { HTTP } from "./base";

const getReaderInfo = (pk, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`c/${pk}`, { params });
};

const getReaderSettings = () => {
  const params = serializeParams({});
  return HTTP.get(`c/settings`, { params });
};

const updateReaderSettings = (data) => {
  return HTTP.patch(`c/settings`, data);
};

export const getDownloadURL = ({ pk, mtime }) => {
  const READER_PATH = getReaderPath(pk);
  return `${READER_PATH}/download/comic-${pk}.cbz?ts=${mtime}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) => {
  const READER_PATH = getReaderPath(pk);
  return `${READER_PATH}/${page}/page.jpg?ts=${mtime}`;
};

export const getComicPageSource = ({ pk, page, mtime }) => {
  const BASE_URL = getReaderBasePath(pk);
  return `${BASE_URL}/${page}/page.jpg?ts=${mtime}`;
};

export const getPdfBookSource = ({ pk, mtime }) => {
  const BASE_URL = getReaderBasePath(pk);
  return `${BASE_URL}/book.pdf?ts=${mtime}`;
};

export default {
  getPdfBookSource,
  getReaderBasePath,
  getReaderInfo,
  getReaderSettings,
  updateReaderSettings,
};
