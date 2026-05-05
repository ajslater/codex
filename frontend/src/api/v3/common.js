import { toRaw } from "vue";

import { useCommonStore } from "@/stores/common";

import { HTTP } from "@/api/v3/base";

const _keepIfNotEmpty = (val) => {
  // Keep flag for filter
  if (val === undefined) return false;
  switch (val?.constructor) {
    case Array:
    case String:
      return val.length > 0;
    case Object:
      return Object.keys(val).length > 0;
    default:
      return true;
  }
};

const _deepClone = (obj, filterEmpty = false) => {
  // Deep clone vue proxyObjects and optionally filter empty elements.
  obj = toRaw(obj);

  const _keep = (val) => {
    // Keep flag for filter, closure for filterEmpty flag.
    return !filterEmpty || _keepIfNotEmpty(val);
  };

  switch (obj?.constructor) {
    case Array:
      return obj.map((v) => _deepClone(v, filterEmpty)).filter(_keep);
    case Object: {
      const result = {};
      for (const [key, val] of Object.entries(obj)) {
        const clonedVal = _deepClone(val, filterEmpty);
        if (_keep(clonedVal)) result[key] = clonedVal;
      }
      return result;
    }
    default:
      return obj;
  }
};

const _jsonSerialize = (params) => {
  // Since axios 1.0 I've had to manually serialize complex objects. Also with xior.
  for (const [key, value] of Object.entries(params)) {
    switch (value?.constructor) {
      case Array:
      case Object:
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

// Public alias: deep-clone a Vue reactive (or plain) object/array,
// recursively unwrapping proxies via ``toRaw`` at every level.
// Prefer this over ``structuredClone`` when the source might be a
// Pinia / Vue reactive value — structuredClone trips ``DataCloneError``
// on certain reactive Array proxies (see ``getMetadata`` history).
export const deepClone = (obj) => _deepClone(obj, false);

export const serializeParams = (data, ts, filterEmpty = true) => {
  const params = _deepClone(data, filterEmpty) || {};
  _jsonSerialize(params);
  _addTimestamp(params, ts);
  return params;
};

export const getDownloadIOSPWAFix = (href, filename) => {
  /*
   * iOS has a download bug inside PWAs. The user is trapped in the
   * download screen and cannot return to the app.
   * https://developer.apple.com/forums/thread/95911
   * This works around that by creating temporary blob link which
   * makes the PWA display browser back controls
   */
  HTTP.get(href, { responseType: "blob" })
    .then((response) => {
      const link = document.createElement("a");
      const blob = new Blob([response.data], {
        type: "application/octet-stream",
      });
      // ``createObjectURL`` returns a string ``blob:...`` URL;
      // ``revokeObjectURL`` must be called on that same string,
      // not on the underlying Blob. The original code passed the
      // Blob, which silently no-op'd and leaked the object URL on
      // every iOS PWA download.
      const objectUrl = globalThis.URL.createObjectURL(blob);
      link.href = objectUrl;
      link.download = filename;
      link.click();
      globalThis.URL.revokeObjectURL(objectUrl);
      return link.remove();
    })
    .catch(console.warn);
};

export const getMtime = (groups, settings, options = {}) => {
  const params = serializeParams({ groups, ...settings }, Date.now());
  return HTTP.get("/mtime", { params, ...options });
};

export const getOPDSURLs = () => HTTP.get("/opds-urls");

export const getVersions = (ts) => HTTP.get("/version", { params: { ts } });
