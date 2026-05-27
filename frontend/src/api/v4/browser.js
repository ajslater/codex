import { toRaw } from "vue";

import { HTTP } from "@/api/v4/base";
import { serializeParams } from "@/api/v4/common";

const V4_BASE = "/api/v4/";
const APP_BASE = (() => globalThis.CODEX?.APP_PATH || "/")();

/*
 * v4 path scheme — Option A: ``/browse/{collection}[/{parentIds}]``.
 * No magic ``pks=0``, no single-char group codes. Root listings omit
 * the parent-IDs segment entirely. Page is a query param, not a path
 * segment.
 */
const GROUP_TO_COLLECTION = Object.freeze({
  p: "publishers",
  i: "imprints",
  s: "series",
  v: "volumes",
  c: "comics",
  f: "folders",
  a: "arcs",
  r: "publishers",
});

const _collection = (group) => GROUP_TO_COLLECTION[group] || group;

const _segment = (group, pks) => {
  const collection = _collection(group);
  if (!pks || !pks.length || pks.every((pk) => !pk)) return collection;
  return `${collection}/${pks.join(",")}`;
};

const getBrowserHrefPath = ({ group, pks, query, ts }) => {
  const params = serializeParams(query, ts);
  const queryString = new URLSearchParams(params).toString();
  return { hrefPath: _segment(group, pks), queryString };
};

export const getBrowserHref = ({ group, pks, query }) => {
  const { hrefPath, queryString } = getBrowserHrefPath({ group, pks, query });
  return `${APP_BASE}${hrefPath}/1?${queryString}`;
};

export const getCoverSrc = ({ coverPk, coverCustomPk, group }, ts) => {
  const query = ts ? `?ts=${ts}` : "";
  if (coverCustomPk) {
    return `${V4_BASE}covers/custom/${coverCustomPk}${query}`;
  }
  // ``coverPk`` is the representative comic pk pre-annotated by the
  // browser response. v4 keeps the per-comic source so the URL is
  // cacheable across cards that share a representative.
  const source = group && group !== "c" ? "comic" : "comic";
  return `${V4_BASE}covers/${source}/${coverPk}${query}`;
};

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
  return HTTP.get(`/browse/${_segment(group, pks)}/choices`, {
    params,
    ...options,
  });
};

export const getFilterChoices = (
  { group, pks, fieldName },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/browse/${_segment(group, pks)}/choices/${fieldName}`, {
    params,
    ...options,
  });
};

export const getBrowserPage = (
  { group, pks, page },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams({ ...data, page }, ts, false);
  return HTTP.get(`/browse/${_segment(group, pks)}`, { params, ...options });
};

export const getMetadata = ({ group, pks }, settings) => {
  const { mtime, ...data } = toRaw(settings) || {};
  const params = serializeParams(data, mtime, false);
  return HTTP.get(`/browse/${_segment(group, pks)}/metadata`, { params });
};

const _collectionSettingsBase = (group) =>
  `/browse/${_collection(group || "r")}/settings`;

export const getSettings = (data) => {
  const params = serializeParams(data);
  const group = data?.group;
  return HTTP.get(_collectionSettingsBase(group), { params });
};

export const updateSettings = (settings) => {
  const params = serializeParams(settings, undefined, false);
  return HTTP.patch(_collectionSettingsBase(settings?.group), { params });
};

export const resetSettings = (settings) =>
  HTTP.delete(_collectionSettingsBase(settings?.group));

export const getGroupDownloadURL = ({ group, pks }, fn, settings, ts) => {
  const { show: _show, ...query } = settings;
  const { queryString } = getBrowserHrefPath({ group, pks, query, ts });
  const encoded = encodeURIComponent(fn);
  return `${V4_BASE}browse/${_segment(group, pks)}/download/${encoded}?${queryString}`;
};

export const updateGroupBookmarks = ({ group, ids }, settings, updates) => {
  const params = serializeParams(settings);
  const queryString = new URLSearchParams(params).toString();
  const body = updates.fitTo === null ? { ...updates, fitTo: "" } : updates;
  return HTTP.patch(
    `/browse/${_segment(group, ids)}/bookmark?${queryString}`,
    body,
  );
};

export const getLazyImport = ({ group, pks }) =>
  HTTP.post(`/browse/${_segment(group, pks)}/import`);

export const forceUpdateGroup = ({ group, ids }, settings) => {
  const params = serializeParams(settings);
  const queryString = new URLSearchParams(params).toString();
  return HTTP.post(
    `/browse/${_segment(group, ids)}/refresh?${queryString}`,
  );
};

/*
 * Saved-settings paths are per-collection in v4. Callers that don't
 * care about scope (the existing browser store treats saved settings
 * as global) get the root publishers collection by default; consumers
 * that want per-collection scope can pass the group letter.
 */
const _collectionSavedSettings = (group) =>
  `/browse/${_collection(group || "r")}/saved-settings`;

export const getSavedSettingsList = (group) =>
  HTTP.get(_collectionSavedSettings(group));

export const saveSettings = (name, group) =>
  HTTP.post(_collectionSavedSettings(group), { name });

export const loadSavedSettings = (pk, group) =>
  HTTP.get(`${_collectionSavedSettings(group)}/${pk}`);

export const deleteSavedSettings = (pk, group) =>
  HTTP.delete(`${_collectionSavedSettings(group)}/${pk}`);
