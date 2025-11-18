import deepClone from "deep-clone";

import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

const getBrowserHrefPath = ({ group, pks, query, ts }) => {
  const params = serializeParams(query, ts);
  const queryString = new URLSearchParams(params).toString();
  const pkList = pks.join(",");
  return { hrefPath: `${group}/${pkList}`, queryString };
};

export const getBrowserHref = ({ group, pks, query }) => {
  const base = globalThis.CODEX.APP_PATH;
  const { hrefPath, queryString } = getBrowserHrefPath({
    group,
    pks,
    query,
  });
  return `${base}${hrefPath}/1?${queryString}`;
};

export const getCoverSrc = ({ group, pks }, settings, ts) => {
  const base = globalThis.CODEX.API_V3_PATH;
  delete settings.show;
  const { hrefPath, queryString } = getBrowserHrefPath({
    group,
    pks,
    query: settings,
    ts,
  });
  return `${base}${hrefPath}/cover.webp?${queryString}`;
};

const getAvailableFilterChoices = ({ group, pks }, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices_available`, { params });
};

const getFilterChoices = ({ group, pks }, fieldName, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices/${fieldName}`, { params });
};

const getBrowserPage = ({ group, pks, page }, data, ts) => {
  const params = serializeParams(data, ts, false);
  return HTTP.get(`/${group}/${pks}/${page}`, { params });
};

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const mtime = settings.mtime;
  const data = deepClone(settings);
  delete data.mtime;
  const params = serializeParams(data, mtime, false);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

const getSettings = (data) => {
  const params = serializeParams(data);
  return HTTP.get("/r/settings", { params });
};

const updateSettings = (settings) => {
  const params = serializeParams(settings, undefined, false);
  return HTTP.patch("/r/settings", { params });
};

export const getGroupDownloadURL = ({ group, pks }, fn, settings, ts) => {
  const base = globalThis.CODEX.API_V3_PATH;
  delete settings.show;
  const { hrefPath, queryString } = getBrowserHrefPath({
    group,
    pks,
    query: settings,
    ts,
  });
  fn = encodeURIComponent(fn);
  return `${base}${hrefPath}/download/${fn}?${queryString}`;
};

const updateGroupBookmarks = ({ group, ids }, settings, updates) => {
  const params = serializeParams(settings);
  const queryString = new URLSearchParams(params).toString();
  if (updates.fitTo === null) {
    updates.fitTo = "";
  }
  const pkList = ids.join(",");
  return HTTP.patch(`${group}/${pkList}/bookmark?${queryString}`, updates);
};

const getLazyImport = ({ group, pks }) => {
  return HTTP.get(`/${group}/${pks}/import`);
};

export default {
  getAvailableFilterChoices,
  getBrowserHref,
  getCoverSrc,
  getFilterChoices,
  getGroupDownloadURL,
  getMetadata,
  getSettings,
  getBrowserPage,
  getLazyImport,
  updateGroupBookmarks,
  updateSettings,
};
