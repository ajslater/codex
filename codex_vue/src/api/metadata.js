import { ajax } from "./base";

const COMIC_BASE = "/comic";

const getComicMetadata = (pk) => {
  return ajax("get", `${COMIC_BASE}/${pk}/metadata`);
};

export const getDownloadURL = (pk) => {
  return `/api{$COMIC_BASE}/${pk}/archive.cbz`;
};

export default {
  getComicMetadata,
  getDownloadURL,
};
