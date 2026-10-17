import { HTTP, V4_BASE } from "@/api/v4/base";
import { serializeParams } from "@/api/v4/common";

export const getSettings = (pk, scopes, storyArcPk) => {
  const queryParams = { scopes: scopes.join(",") };
  if (storyArcPk) {
    queryParams.story_arc_pk = storyArcPk;
  }
  const params = serializeParams(queryParams);
  return HTTP.get(pk ? `/comics/${pk}/reader-settings` : "/reader/settings", {
    params,
  });
};

export const updateSettings = (data) =>
  HTTP.patch(
    data?.pk ? `/comics/${data.pk}/reader-settings` : "/reader/settings",
    data,
  );

export const resetSettings = (data) =>
  HTTP.delete(
    data?.pk ? `/comics/${data.pk}/reader-settings` : "/reader/settings",
    { data },
  );

export const getReaderInfo = (pk, data, ts, options = {}) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/reader/comics/${pk}`, { params, ...options });
};

export const getComicPageSource = ({ pk, page, mtime, serve }) => {
  let url = `${V4_BASE}comics/${pk}/pages/${page}?ts=${mtime}`;
  if (serve && serve !== "auto") {
    url += `&serve=${serve}`;
  }
  return url;
};

export const getComicDownloadURL = ({ pk }, fn, ts) => {
  const encoded = fn ? encodeURIComponent(fn) : `comic-${pk}.cbz`;
  return `comics/${pk}/download/${encoded}?ts=${ts}`;
};

export const getDownloadPageURL = ({ pk, page, mtime }) =>
  `comics/${pk}/pages/${page}?ts=${mtime}`;

export const getPDFInBrowserURL = ({ pk, mtime }) =>
  `${V4_BASE}comics/${pk}/download/comic-${pk}.pdf?ts=${mtime}`;

export const updateBookmark = (pk, body) =>
  HTTP.patch(`/comics/${pk}/bookmark`, body);
