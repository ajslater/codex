import { ajax, API_PREFIX } from "./base";

const COMIC_BASE = "/comic";

const getComicOpened = (pk) => {
  return ajax("get", `${COMIC_BASE}/${pk}`);
};

const setComicBookmark = ({ pk, pageNumber }) => {
  return ajax("patch", `${COMIC_BASE}/${pk}/${pageNumber}/bookmark`);
};

const setComicSettings = ({ pk, data }) => {
  return ajax("patch", `${COMIC_BASE}/${pk}/settings`, data);
};

const setComicDefaultSettings = (data) => {
  return ajax("put", `${COMIC_BASE}/settings`, data);
};

export const getComicPageSource = ({ pk, pageNumber }) => {
  return `${API_PREFIX}${COMIC_BASE}/${pk}/${pageNumber}/p.jpg`;
};

export default {
  getComicOpened,
  getComicPageSource,
  setComicBookmark,
  setComicSettings,
  setComicDefaultSettings,
};
