import { HTTP } from "@/api/v3/base";
import { serializeParams } from "@/api/v3/common";

const _getBookPath = (pk) => `c/${pk}`;

export const getSettings = (pk, scopes, storyArcPk) => {
  const basePath = pk ? `/${_getBookPath(pk)}/settings` : "/c/settings";
  const queryParams = { scopes: scopes.join(",") };
  if (storyArcPk) {
    queryParams.story_arc_pk = storyArcPk;
  }
  const params = serializeParams(queryParams);
  return HTTP.get(basePath, { params });
};

export const updateSettings = (data) => HTTP.patch("/c/settings", data);

export const resetSettings = (data) => HTTP.delete("/c/settings", { data });

export const getReaderInfo = (pk, data, ts, options = {}) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${_getBookPath(pk)}`, { params, ...options });
};

const _getReaderAPIPath = (pk) =>
  globalThis.CODEX.API_V3_PATH + _getBookPath(pk);

export const getComicPageSource = ({ pk, page, mtime }) => {
  const bookAPIPath = _getReaderAPIPath(pk);
  return `${bookAPIPath}/${page}/page.jpg?ts=${mtime}`;
};

export const getComicDownloadURL = ({ pk }, fn, ts) => {
  // Consumed via ``HTTP.get`` (iOS-PWA download fix), so the ``baseURL``
  // prefix is added by xior — no leading slash here.
  const bookPath = _getBookPath(pk);
  fn = fn ? encodeURIComponent(fn) : `comic-${pk}.cbz`;
  return `${bookPath}/download/${fn}?ts=${ts}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) => {
  // Consumed via ``HTTP.get``, so no leading slash (see above).
  const bookPath = _getBookPath(pk);
  return `${bookPath}/${page}/page.jpg?ts=${mtime}`;
};

export const getPDFInBrowserURL = ({ pk, mtime }) => {
  // Consumed by ``<embed src=...>``, not ``HTTP.get`` — needs an
  // absolute path so the browser doesn't resolve it relative to the
  // current SPA route.
  const bookPath = _getBookPath(pk);
  return `/${bookPath}/book.pdf?ts=${mtime}`;
};
