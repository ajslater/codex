import { ajax, API_PREFIX } from "./base";

const COMIC_BASE = "/comic";

const getComicMetadata = (pk) => {
  return ajax("get", `${COMIC_BASE}/${pk}/metadata`);
};

export const getDownloadURL = (pk) => {
  return `${API_PREFIX}${COMIC_BASE}/${pk}/archive.cbz`;
};

export default {
  getComicMetadata,
  getDownloadURL,
};
