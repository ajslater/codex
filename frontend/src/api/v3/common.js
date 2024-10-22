import { useCommonStore } from "@/stores/common";

import { HTTP } from "./base";

const map = (obj, func) => {
  // Generic map for arrays and objects
  switch (obj?.constructor) {
    case Array:
      return obj.map(func);
    case Object:
      return Object.fromEntries(
        Object.entries(obj).map(([key, val]) => [key, func(val, key)]),
      );
    default:
      return obj;
  }
};

const filter = (obj, func) => {
  // Generic filter for arrays and objects
  switch (obj?.constructor) {
    case Array:
      return obj.filter(func);
    case Object:
      return Object.fromEntries(
        Object.entries(obj).filter(([key, val]) => func(val, key)),
      );
    default:
      return obj;
  }
};

const keep = (obj) => {
  // Remove empty strings, arrays, and objects.
  switch (obj?.constructor) {
    case Array:
    case String:
      return obj.length > 0;
    case Object:
      return Object.keys(obj).length > 0;
    default:
      return obj !== undefined;
  }
};

const _filterEmptyParams = (obj) => {
  // Deep copy params without empty params.
  switch (obj?.constructor) {
    case Array:
    case Object:
      return filter(map(obj, _filterEmptyParams), keep);
    default:
      return keep(obj) ? obj : undefined;
  }
};

const _jsonSerialize = (params) => {
  // Since axios 1.0 I have to manually serialize complex objects
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "object" || Array.isArray(value)) {
      params[key] = JSON.stringify(value);
    }
  }
};

const _addTimestamp = (params, ts) => {
  if (!ts) {
    ts = useCommonStore().timestamp;
  }
  params.ts = ts;
};

export const serializeParams = (data, ts) => {
  const params = _filterEmptyParams(data) || {};
  _jsonSerialize(params);
  _addTimestamp(params, ts);
  return params;
};

export const getDownloadIOSPWAFix = (href, filename) => {
  // iOS has a download bug inside PWAs. The user is trapped in the
  // download screen and cannot return to the app.
  // https://developer.apple.com/forums/thread/95911
  // This works around that by creating temporary blob link which
  // makes the PWA display browser back controls
  HTTP.get(href, { responseType: "blob" })
    .then((response) => {
      const link = document.createElement("a");
      const blob = new Blob([response.data], {
        type: "application/octet-stream",
      });
      link.href = window.URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      window.URL.revokeObjectURL(response.data);
      return link.remove();
    })
    .catch(console.warn);
};

const getMtime = (groups, settings) => {
  const params = serializeParams({ groups, ...settings }, Date.now());
  return HTTP.get("/mtime", { params });
};
const getOPDSURLs = () => {
  return HTTP.get("/opds-urls");
};

const getVersions = (ts) => {
  const params = { ts };
  return HTTP.get("/version", { params });
};

const getBanner = () => {
  const params = serializeParams();
  return HTTP.get("/banner", { params });
};

export default {
  getDownloadIOSPWAFix,
  getMtime,
  getOPDSURLs,
  getVersions,
  getBanner,
};
