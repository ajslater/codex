import deepClone from "deep-clone";

import { useCommonStore } from "@/stores/common";

import { HTTP } from "./base";

const _json_serialize = (params) => {
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
  const params = deepClone(data) || {};
  _json_serialize(params);
  _addTimestamp(params, ts);
  return params;
};

const getDownloadIOSPWAFix = (href, fileName) => {
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
      link.download = fileName;
      link.click();
      return window.URL.revokeObjectURL(response.data);
    })
    .catch(console.warn);
};

export const getReaderPath = (pk) => {
  return `c/${pk}`;
};

export const getReaderBasePath = (pk) => {
  return window.CODEX.API_V3_PATH + getReaderPath(pk);
};

export const getBookInBrowserURL = ({ pk, mtime }) => {
  const BASE_URL = window.CODEX.APP_PATH + getReaderPath(pk);
  return `${BASE_URL}/book.pdf?ts=${mtime}`;
};

export const getMtime = (groups, settings) => {
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

const updateGroupBookmarks = ({ group, ids }, data) => {
  if (data.fitTo === null) {
    data.fitTo = "";
  }
  const pks = ids.join(",");
  return HTTP.patch(`${group}/${pks}/bookmark`, data);
};

export default {
  getDownloadIOSPWAFix,
  getBookInBrowserURL,
  getMtime,
  getOPDSURLs,
  getReaderBasePath,
  getReaderPath,
  getVersions,
  updateGroupBookmarks,
};
