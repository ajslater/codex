import { toRaw } from "vue";

import { APP_BASE, HTTP, V4_BASE } from "@/api/v4/base";
import { serializeParams } from "@/api/v4/common";

/*
 * v4 path scheme — Option A: ``/browse/{collection}[/{parentIds}]``.
 * No magic ``pks=0``, no single-char collection codes. Root listings omit
 * the parent-IDs segment entirely. Page is a query param, not a path
 * segment.
 */
// Only the synthetic ``root`` resolves to its top collection (publishers);
// every other collection value is its own segment.
const _collection = (collection) =>
  collection === "root" ? "publishers" : collection;

/*
 * Normalize a pks input — Vue Router params arrive as strings
 * (``"0"`` for root, ``"5,7"`` for parented), while internal helpers
 * sometimes pass arrays. Returns the cleaned list of non-zero
 * integers (as strings); empty array means root.
 */
const _normalizePks = (pks) => {
  if (pks === undefined || pks === null) return [];
  const raw = Array.isArray(pks) ? pks : String(pks).split(",");
  const cleaned = [];
  for (const entry of raw) {
    const str = String(entry).trim();
    if (!str || str === "0") continue;
    cleaned.push(str);
  }
  return cleaned;
};

const _segment = (collection, pks) => {
  const seg = _collection(collection);
  const ids = _normalizePks(pks);
  if (!ids.length) return seg;
  return `${seg}/${ids.join(",")}`;
};

const getBrowserHrefPath = ({ collection, pks, query, ts }) => {
  const params = serializeParams(query, ts);
  const queryString = new URLSearchParams(params).toString();
  return { hrefPath: _segment(collection, pks), queryString };
};

export const getBrowserHref = ({ collection, pks, query }) => {
  const { hrefPath, queryString } = getBrowserHrefPath({
    collection,
    pks,
    query,
  });
  return `${APP_BASE}${hrefPath}/1?${queryString}`;
};

export const getCoverSrc = ({ coverPk, coverCustomPk }, ts) => {
  const query = ts ? `?ts=${ts}` : "";
  if (coverCustomPk) {
    return `${V4_BASE}covers/custom/${coverCustomPk}${query}`;
  }
  // ``coverPk`` is the representative comic pk pre-annotated by the
  // browser response. v4 keeps the per-comic source so the URL is
  // cacheable across cards that share a representative.
  return `${V4_BASE}covers/comic/${coverPk}${query}`;
};

const PLACEHOLDER_BY_GROUP = Object.freeze({
  publishers: "publisher",
  imprints: "imprint",
  series: "series",
  volumes: "volume",
  folders: "folder",
  arcs: "story-arc",
  comics: "comic",
});

export const getPlaceholderSrc = (collection) => {
  const name = PLACEHOLDER_BY_GROUP[collection] ?? "comic";
  return `${globalThis.CODEX.STATIC}img/${name}.svg`;
};

export const getAvailableFilterChoices = (
  { collection, pks },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/browse/${_segment(collection, pks)}/choices`, {
    params,
    ...options,
  });
};

export const getFilterChoices = (
  { collection, pks, fieldName },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/browse/${_segment(collection, pks)}/choices/${fieldName}`, {
    params,
    ...options,
  });
};

export const getBrowserPage = (
  { collection, pks, page },
  data,
  ts,
  options = {},
) => {
  const params = serializeParams({ ...data, page }, ts, false);
  return HTTP.get(`/browse/${_segment(collection, pks)}`, {
    params,
    ...options,
  });
};

/*
 * Lightweight {mtime, count} probe for the library.changed refresh gate.
 * Same route + settings as getBrowserPage so both signals match the page;
 * a fresh ts busts any cache so the probe reflects the current DB.
 */
export const getBrowserHead = ({ collection, pks }, data, options = {}) => {
  const params = serializeParams(data, Date.now(), false);
  return HTTP.get(`/browse/${_segment(collection, pks)}/head`, {
    params,
    ...options,
  });
};

export const getMetadata = ({ collection, pks }, settings) => {
  const { mtime, ...data } = toRaw(settings) || {};
  const params = serializeParams(data, mtime, false);
  return HTTP.get(`/browse/${_segment(collection, pks)}/metadata`, { params });
};

const _collectionSettingsBase = (collection) =>
  `/browse/${_collection(collection || "root")}/settings`;

export const getSettings = (data) => {
  const params = serializeParams(data);
  const collection = data?.collection;
  return HTTP.get(_collectionSettingsBase(collection), { params });
};

export const updateSettings = (settings) => {
  const params = serializeParams(settings, undefined, false);
  return HTTP.patch(_collectionSettingsBase(settings?.collection), { params });
};

export const resetSettings = (settings) =>
  HTTP.delete(_collectionSettingsBase(settings?.collection));

export const getCollectionDownloadURL = (
  { collection, pks },
  fn,
  settings,
  ts,
) => {
  const { show: _show, ...query } = settings;
  const { queryString } = getBrowserHrefPath({ collection, pks, query, ts });
  const encoded = encodeURIComponent(fn);
  return `${V4_BASE}browse/${_segment(collection, pks)}/download/${encoded}?${queryString}`;
};

export const updateCollectionBookmarks = (
  { collection, ids },
  settings,
  updates,
) => {
  const params = serializeParams(settings);
  const queryString = new URLSearchParams(params).toString();
  const body = updates.fitTo === null ? { ...updates, fitTo: "" } : updates;
  return HTTP.patch(
    `/browse/${_segment(collection, ids)}/bookmark?${queryString}`,
    body,
  );
};

export const getLazyImport = ({ collection, pks }) =>
  HTTP.post(`/browse/${_segment(collection, pks)}/import`);

export const forceUpdateCollection = ({ collection, ids }, settings) => {
  const params = serializeParams(settings);
  const queryString = new URLSearchParams(params).toString();
  return HTTP.post(
    `/browse/${_segment(collection, ids)}/refresh?${queryString}`,
  );
};

/*
 * Saved-settings paths are per-collection in v4. Callers that don't
 * care about scope (the existing browser store treats saved settings
 * as global) get the root publishers collection by default; consumers
 * that want per-collection scope can pass the collection value.
 */
const _collectionSavedSettings = (collection) =>
  `/browse/${_collection(collection || "root")}/saved-settings`;

export const getSavedSettingsList = (collection) =>
  HTTP.get(_collectionSavedSettings(collection));

export const saveSettings = (name, collection) =>
  HTTP.post(_collectionSavedSettings(collection), { name });

export const loadSavedSettings = (pk, collection) =>
  HTTP.get(`${_collectionSavedSettings(collection)}/${pk}`);

export const deleteSavedSettings = (pk, collection) =>
  HTTP.delete(`${_collectionSavedSettings(collection)}/${pk}`);
