import { serializeParams } from "@/api/v3/common";

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

// URLS
const _getReaderPath = (pk) => {
  return `c/${pk}`;
};

const _getReaderAPIPath = (pk) => {
  return window.CODEX.API_V3_PATH + _getReaderPath(pk);
};

export const getComicPageSource = ({ pk, page, mtime }) => {
  const BASE_URL = _getReaderAPIPath(pk);
  return `${BASE_URL}/${page}/page.jpg?ts=${mtime}`;
};

export const getDownloadURL = ({ pk, mtime }) => {
  // Gets used by an HTTP.get so already has base path.
  const READER_PATH = _getReaderPath(pk);
  return `${READER_PATH}/download/comic-${pk}.cbz?ts=${mtime}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) => {
  // Gets used by an HTTP.get so already has base path.
  const READER_PATH = _getReaderPath(pk);
  return `${READER_PATH}/${page}/page.jpg?ts=${mtime}`;
};

export const getPDFInBrowserURL = ({ pk, mtime }) => {
  const READER_API_PATH = _getReaderAPIPath(pk);
  return `${READER_API_PATH}/book.pdf?ts=${mtime}`;
};

export default {
  getReaderInfo,
  getReaderSettings,
  getPDFInBrowserURL,
  updateReaderSettings,
};
