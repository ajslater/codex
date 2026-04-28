import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";
import { toRaw } from "vue";

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

export const getCoverSrc = ({ coverPk, coverCustomPk }, ts) => {
  const base = globalThis.CODEX.API_V3_PATH;
  const query = ts ? `?ts=${ts}` : "";
  if (coverCustomPk) {
    return `${base}custom_cover/${coverCustomPk}/cover.webp${query}`;
  }
  return `${base}c/${coverPk}/cover.webp${query}`;
};

// Mirror of MISSING_COVER_NAME_MAP in codex/views/const.py.
// Root group "r" never appears as a card group, so it's intentionally
// absent — unknown letters fall back to the comic placeholder.
const PLACEHOLDER_BY_GROUP = Object.freeze({
  p: "publisher",
  i: "imprint",
  s: "series",
  v: "volume",
  f: "folder",
  a: "story-arc",
  c: "comic",
});

export const getPlaceholderSrc = (group) => {
  const name = PLACEHOLDER_BY_GROUP[group] ?? "comic";
  return `${globalThis.CODEX.STATIC}img/${name}.svg`;
};

const getAvailableFilterChoices = ({ group, pks }, data, ts, options = {}) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices_available`, { params, ...options });
};

/* eslint-disable max-params */
const getFilterChoices = (
  { group, pks },
  fieldName,
  data,
  ts,
  options = {},
) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices/${fieldName}`, {
    params,
    ...options,
  });
};
/* eslint-enable max-params */

const getBrowserPage = ({ group, pks, page }, data, ts, options = {}) => {
  const params = serializeParams(data, ts, false);
  return HTTP.get(`/${group}/${pks}/${page}`, { params, ...options });
};

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const rawSettings = toRaw(settings) || {};
  const filters = toRaw(rawSettings?.filters) || {};
  const mtime = rawSettings?.mtime;
  const data = structuredClone({ ...rawSettings, filters });
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

const resetSettings = () => {
  return HTTP.delete("/r/settings");
};

export const getGroupDownloadURL = ({ group, pks }, fn, settings, ts) => {
  const base = globalThis.CODEX.API_V3_PATH;
  // Strip ``show`` without mutating the caller's settings object;
  // the previous ``delete settings.show`` was a silent side-effect
  // that broke any caller relying on its settings object surviving
  // a download-URL build.
  const { show: _show, ...query } = settings;
  const { hrefPath, queryString } = getBrowserHrefPath({
    group,
    pks,
    query,
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

const getSavedSettingsList = () => {
  return HTTP.get("/r/settings/saved");
};

const saveSettings = (name) => {
  return HTTP.post("/r/settings/saved", { name });
};

const loadSavedSettings = (pk) => {
  return HTTP.get(`/r/settings/saved/${pk}`);
};

const deleteSavedSettings = (pk) => {
  return HTTP.delete(`/r/settings/saved/${pk}`);
};

export default {
  getAvailableFilterChoices,
  getBrowserHref,
  getCoverSrc,
  getPlaceholderSrc,
  getFilterChoices,
  getGroupDownloadURL,
  getMetadata,
  getSettings,
  getBrowserPage,
  getLazyImport,
  updateGroupBookmarks,
  resetSettings,
  updateSettings,
  getSavedSettingsList,
  saveSettings,
  loadSavedSettings,
  deleteSavedSettings,
};
