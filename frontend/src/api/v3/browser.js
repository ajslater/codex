import { toRaw } from "vue";

import { HTTP } from "@/api/v3/base";
import { serializeParams } from "@/api/v3/common";

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

export const getAvailableFilterChoices = (
  { group, pks },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices_available`, { params, ...options });
};

/* eslint-disable max-params */
export const getFilterChoices = (
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

export const getBrowserPage = (
  { group, pks, page },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams(data, ts, false);
  return HTTP.get(`/${group}/${pks}/${page}`, { params, ...options });
};

export const getMetadata = ({ group, pks }, settings) => {
  // Pull ``mtime`` out as the timestamp; ``serializeParams`` deep-clones
  // the rest via ``_deepClone`` (which calls ``toRaw`` at every level),
  // so we don't need ``structuredClone`` here — and can't safely use it,
  // since the reactive filter arrays from the Pinia store don't always
  // survive a structured clone (DataCloneError on ``[object Array]``).
  const pkList = pks.join(",");
  const { mtime, ...data } = toRaw(settings) || {};
  const params = serializeParams(data, mtime, false);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

export const getSettings = (data) => {
  const params = serializeParams(data);
  return HTTP.get("/r/settings", { params });
};

export const updateSettings = (settings) => {
  const params = serializeParams(settings, undefined, false);
  return HTTP.patch("/r/settings", { params });
};

export const resetSettings = () => HTTP.delete("/r/settings");

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

export const updateGroupBookmarks = ({ group, ids }, settings, updates) => {
  const params = serializeParams(settings);
  const queryString = new URLSearchParams(params).toString();
  // Backend rejects the JSON literal ``null`` for ``fitTo``; normalise
  // without mutating the caller's reactive update payload.
  const body = updates.fitTo === null ? { ...updates, fitTo: "" } : updates;
  const pkList = ids.join(",");
  return HTTP.patch(`/${group}/${pkList}/bookmark?${queryString}`, body);
};

export const getLazyImport = ({ group, pks }) =>
  HTTP.get(`/${group}/${pks}/import`);

export const getSavedSettingsList = () => HTTP.get("/r/settings/saved");

export const saveSettings = (name) => HTTP.post("/r/settings/saved", { name });

export const loadSavedSettings = (pk) => HTTP.get(`/r/settings/saved/${pk}`);

export const deleteSavedSettings = (pk) =>
  HTTP.delete(`/r/settings/saved/${pk}`);
