import { ajax, API_PREFIX } from "./base";

const COMIC_BASE = "/comic";
const METADATA_BASE = "/metadata";

const getComicMetadata = (group, pk) => {
  return ajax("get", `${METADATA_BASE}/${group}/${pk}`);
};

export const getDownloadURL = (pk) => {
  return `${API_PREFIX}${COMIC_BASE}/${pk}/archive.cbz`;
};

export default {
  getComicMetadata,
  getDownloadURL,
};
