import { ajax } from "./base";

export const getComicBaseURL = (pk) => {
  return `${window.CODEX.API_V2_PATH}c/${pk}`;
};

const getComicOpened = (pk, timestamp) => {
  return ajax("get", `c/${pk}?ts=${timestamp}`);
};

const setComicBookmark = ({ pk, page }) => {
  return ajax("patch", `c/${pk}/${page}/bookmark`);
};

const getComicSettings = (pk, timestamp) => {
  return ajax("get", `c/${pk}/settings?ts=${timestamp}`);
};

const setComicSettings = ({ pk, data }) => {
  return ajax("patch", `c/${pk}/settings`, data);
};

const setComicDefaultSettings = ({ pk, data }) => {
  return ajax("put", `c/${pk}/settings`, data);
};

export const getDownloadURL = (pk, timestamp) => {
  const COMIC_BASE_URL = getComicBaseURL(pk);
  return `${COMIC_BASE_URL}/comic.cbz?ts=${timestamp}`;
};

export const getComicPageSource = ({ pk, page }, timestamp) => {
  const COMIC_BASE_URL = getComicBaseURL(pk);
  return `${COMIC_BASE_URL}/${page}/p.jpg?ts=${timestamp}`;
};

export default {
  getComicOpened,
  setComicBookmark,
  getComicSettings,
  setComicSettings,
  setComicDefaultSettings,
  getComicBaseURL,
};
