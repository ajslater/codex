import { useCommonStore } from "@/stores/common";

import { HTTP } from "./base";

const downloadIOSPWAFix = (href, fileName) => {
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
  return `${BASE_URL}/book.pdf?mtime=${mtime}`;
};

const getVersions = (ts) => {
  const params = { ts };
  return HTTP.get("/version", { params });
};

const getOPDSURLs = () => {
  return HTTP.get("/opds-urls");
};

const _trimObject = (obj) => {
  // Remove empty and undefined objects because they're default values.
  if (obj === undefined || obj === null) {
    return {};
  }
  const isArray = Array.isArray(obj);
  const result = isArray ? [] : {};
  for (const [key, val] of Object.entries(obj)) {
    if (val === undefined || val === null) {
      continue;
    }
    const isValObject = val && typeof val === "object";
    const trimmedVal = isValObject ? _trimObject(val) : val;
    if (!isValObject || Object.keys(trimmedVal).length > 0) {
      if (isArray) {
        result.push(trimmedVal);
      } else {
        result[key] = trimmedVal;
      }
    }
  }
  return result;
};

const _serialize = (params, jsonKeys) => {
  // Since axios 1.0 I have to manually serialize complex objects
  if (jsonKeys) {
    for (const key of jsonKeys) {
      if (params[key]) {
        params[key] = JSON.stringify(params[key]);
      }
    }
  }
};

const _addTimestamp = (params, ts) => {
  if (!ts) {
    ts = useCommonStore().timestamp;
  }
  params.ts = ts;
};

export const serializeParams = (data, ts, jsonKeys) => {
  const params = _trimObject(data);
  /* TODO test
  if (params.q === "") {
    delete params.q;
  }
  */
  _serialize(params, jsonKeys);
  _addTimestamp(params, ts);
  return params;
};

export default {
  downloadIOSPWAFix,
  getBookInBrowserURL,
  getReaderBasePath,
  getReaderPath,
  getVersions,
  getOPDSURLs,
  serializeParams,
};
