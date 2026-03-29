import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

const API_READER_SETTINGS_PATH = "/c/settings";

const getGlobalSettings = () => {
  const params = serializeParams({});
  return HTTP.get(API_READER_SETTINGS_PATH, { params });
};

const updateGlobalSettings = (data) => {
  return HTTP.patch(API_READER_SETTINGS_PATH, data);
};

const _getBookPath = (pk) => {
  return `c/${pk}`;
};

const getReaderInfo = (pk, data, ts) => {
  const params = serializeParams(data, ts);
  const bookPath = _getBookPath(pk);
  return HTTP.get(bookPath, { params });
};

const getComicSettings = (pk) => {
  const bookAPIPath = _getBookPath(pk);
  const params = serializeParams({});
  return HTTP.get(`${bookAPIPath}/settings`, { params });
};

const updateComicSettings = (pk, data) => {
  const bookPath = _getBookPath(pk);
  return HTTP.patch(`${bookPath}/settings`, data);
};

const _getReaderAPIPath = (pk) => {
  return globalThis.CODEX.API_V3_PATH + _getBookPath(pk);
};

export const getComicPageSource = ({ pk, page, mtime }) => {
  const bookAPIPath = _getReaderAPIPath(pk);
  return `${bookAPIPath}/${page}/page.jpg?ts=${mtime}`;
};

export const getComicDownloadURL = ({ pk }, fn, ts) => {
  // Gets used by an HTTP.get so already has base path.
  const bookPath = _getBookPath(pk);
  fn = fn ? encodeURIComponent(fn) : `comic-${pk}.cbz`;
  return `${bookPath}/download/${fn}?ts=${ts}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) => {
  // Gets used by an HTTP.get so already has base path.
  const bookPath = _getBookPath(pk);
  return `${bookPath}/${page}/page.jpg?ts=${mtime}`;
};

export const getPDFInBrowserURL = ({ pk, mtime }) => {
  // Raw URL needs leading slash
  const bookPath = _getBookPath(pk);
  return `/${bookPath}/book.pdf?ts=${mtime}`;
};

export default {
  getComicSettings,
  getGlobalSettings,
  getReaderInfo,
  getPDFInBrowserURL,
  updateComicSettings,
  updateGlobalSettings,
};
