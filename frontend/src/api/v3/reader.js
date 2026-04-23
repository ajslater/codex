import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

const _getBookPath = (pk) => {
  return `c/${pk}`;
};

const getSettings = (pk, scopes, storyArcPk) => {
  const basePath = pk ? `${_getBookPath(pk)}/settings` : "c/settings";
  const queryParams = { scopes: scopes.join(",") };
  if (storyArcPk) {
    queryParams.story_arc_pk = storyArcPk;
  }
  const params = serializeParams(queryParams);
  return HTTP.get(basePath, { params });
};

const updateSettings = (data) => {
  return HTTP.patch("c/settings", data);
};

const resetSettings = (data) => {
  return HTTP.delete("c/settings", { data });
};

const getReaderInfo = (pk, data, ts) => {
  const params = serializeParams(data, ts);
  const bookPath = _getBookPath(pk);
  return HTTP.get(bookPath, { params });
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
  getReaderInfo,
  getSettings,
  getPDFInBrowserURL,
  resetSettings,
  updateSettings,
};
