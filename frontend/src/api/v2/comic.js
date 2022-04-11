import { ajax, API_PREFIX } from "./base";

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
  return `${API_PREFIX}/c/${pk}/comic.cbz?ts=${timestamp}`;
};

export const getComicPageSource = ({ pk, page }, timestamp) => {
  return `${API_PREFIX}/c/${pk}/${page}/p.jpg?ts=${timestamp}`;
};

export default {
  getComicOpened,
  setComicBookmark,
  getComicSettings,
  setComicSettings,
  setComicDefaultSettings,
};
