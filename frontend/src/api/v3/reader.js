import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

// URLS
const _getReaderPath = (pk) => {
  return `c/${pk}`;
};

const getReaderInfo = (pk, data, ts) => {
  const params = serializeParams(data, ts);
  const bookPath = _getReaderPath(pk);
  return HTTP.get(bookPath, { params });
};

const getReaderSettings = () => {
  const params = serializeParams({});
  return HTTP.get(`c/settings`, { params });
};

const updateReaderSettings = (data) => {
  return HTTP.patch(`c/settings`, data);
};

const _getReaderAPIPath = (pk) => {
  return window.CODEX.API_V3_PATH + _getReaderPath(pk);
};

export const getComicPageSource = ({ pk, page, mtime }) => {
  const bookAPIPath = _getReaderAPIPath(pk);
  return `${bookAPIPath}/${page}/page.jpg?ts=${mtime}`;
};

export const getComicDownloadURL = ({ pk }, fn, ts) => {
  // Gets used by an HTTP.get so already has base path.
  const bookPath = _getReaderPath(pk);
  if (fn) {
    fn = encodeURIComponent(fn);
  } else {
    fn = `comic-${pk}.cbz`;
  }
  return `${bookPath}/download/${fn}?ts=${ts}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) => {
  // Gets used by an HTTP.get so already has base path.
  const bookPath = _getReaderPath(pk);
  return `${bookPath}/${page}/page.jpg?ts=${mtime}`;
};

export const getPDFInBrowserURL = ({ pk, mtime }) => {
  // Raw URL needs leading slash
  const bookPath = _getReaderPath(pk);
  return `/${bookPath}/book.pdf?ts=${mtime}`;
};

export default {
  getReaderInfo,
  getReaderSettings,
  getPDFInBrowserURL,
  updateReaderSettings,
};
