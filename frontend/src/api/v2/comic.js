import { ajax, API_PREFIX } from "./base";

const getComicOpened = (pk) => {
  return ajax("get", `c/${pk}`);
};

const setComicBookmark = ({ pk, page }) => {
  return ajax("patch", `c/${pk}/${page}/bookmark`);
};

const getComicSettings = (pk) => {
  return ajax("get", `c/${pk}/settings`);
};

const setComicSettings = ({ pk, data }) => {
  return ajax("patch", `c/${pk}/settings`, data);
};

const setComicDefaultSettings = ({ pk, data }) => {
  return ajax("put", `c/${pk}/settings`, data);
};

export const getDownloadURL = (pk) => {
  return `${API_PREFIX}/c/${pk}/archive.cbz`;
};

export const getComicPageSource = ({ pk, page }) => {
  return `${API_PREFIX}/c/${pk}/${page}/p.jpg`;
};

export default {
  getComicOpened,
  setComicBookmark,
  getComicSettings,
  setComicSettings,
  setComicDefaultSettings,
};
