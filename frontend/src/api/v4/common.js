import { toRaw } from "vue";

import { HTTP } from "@/api/v4/base";
import { useCommonStore } from "@/stores/common";

const _keepIfNotEmpty = (val) => {
  if (val === undefined) return false;
  switch (val?.constructor) {
    case Array:
    case String: {
      return val.length > 0;
    }
    case Object: {
      return Object.keys(val).length > 0;
    }
    default: {
      return true;
    }
  }
};

const _deepClone = (obj, shouldFilterEmpty = false) => {
  obj = toRaw(obj);
  const _keep = (val) => !shouldFilterEmpty || _keepIfNotEmpty(val);
  switch (obj?.constructor) {
    case Array: {
      return obj
        .map((v) => _deepClone(v, shouldFilterEmpty))
        .filter((val) => _keep(val));
    }
    case Object: {
      const result = {};
      for (const [key, val] of Object.entries(obj)) {
        const clonedVal = _deepClone(val, shouldFilterEmpty);
        if (_keep(clonedVal)) result[key] = clonedVal;
      }
      return result;
    }
    default: {
      return obj;
    }
  }
};

const _jsonSerialize = (params) => {
  for (const [key, value] of Object.entries(params)) {
    switch (value?.constructor) {
      case Array:
      case Object: {
        params[key] = JSON.stringify(value);
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

export const deepClone = (obj) => _deepClone(obj, false);

export const serializeParams = (data, ts, shouldFilterEmpty = true) => {
  const params = _deepClone(data, shouldFilterEmpty) || {};
  _jsonSerialize(params);
  _addTimestamp(params, ts);
  return params;
};

export const getDownloadIOSPWAFix = (href, filename) => {
  void HTTP.get(href, { responseType: "blob" })
    .then((response) => {
      const link = document.createElement("a");
      const blob = new Blob([response.data], {
        type: "application/octet-stream",
      });
      const objectUrl = URL.createObjectURL(blob);
      link.href = objectUrl;
      link.download = filename;
      link.click();
      URL.revokeObjectURL(objectUrl);
      return link.remove();
    })
    .catch(console.warn);
};

export const getOPDSURLs = () => HTTP.get("/opds-urls");

export const getVersions = (ts) => HTTP.get("/version", { params: { ts } });

export const getMtime = (collections, settings, options = {}) => {
  const params = serializeParams({ collections, ...settings }, Date.now());
  return HTTP.get("/mtime", { params, ...options });
};
