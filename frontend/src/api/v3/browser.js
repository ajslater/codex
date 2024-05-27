import { useCommonStore } from "@/stores/common";

import { HTTP } from "./base";

const JSON_KEYS = ["filters", "show"];
Object.freeze(JSON_KEYS);

// REST ENDPOINTS
//
const trimObject = (obj) => {
  // Remove empty and undefined objects because they're default values.
  const isArray = Array.isArray(obj);
  const result = isArray ? [] : {};
  for (const [key, val] of Object.entries(obj)) {
    if (val === undefined || val === null) {
      continue;
    }
    const isValObject = val && typeof val === "object";
    const trimmedVal = isValObject ? trimObject(val) : val;
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

const preSerialize = (data, ts) => {
  const params = trimObject(data);
  if (params.q === "") {
    delete params.q;
  }
  // Since axios 1.0 I have to manually serialize complex objects
  for (const key of JSON_KEYS) {
    if (params[key]) {
      params[key] = JSON.stringify(params[key]);
    }
  }
  if (!ts) {
    ts = useCommonStore().timestamp;
  }
  params.ts = ts;
  return params;
};

const getAvailableFilterChoices = ({ group, pks }, data, ts) => {
  const params = preSerialize(data, ts);
  return HTTP.get(`/${group}/${pks}/choices_available`, { params });
};

const getFilterChoices = ({ group, pks }, fieldName, data, ts) => {
  const params = preSerialize(data, ts);
  return HTTP.get(`/${group}/${pks}/choices/${fieldName}`, { params });
};

const loadBrowserPage = ({ group, pks, page }, data, ts) => {
  const params = preSerialize(data, ts);
  return HTTP.get(`/${group}/${pks}/${page}`, { params });
};

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const mtime = Math.max(group.mtime, settings.mtime);
  const data = { ...settings };
  delete data.mtime;
  const params = preSerialize(data, mtime);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

const getSettings = (ts) => {
  const params = preSerialize({}, ts);
  return HTTP.get("/r/settings", { params });
};

const setGroupBookmarks = ({ group, ids }, data) => {
  if (data.fitTo === null) {
    data.fitTo = "";
  }
  const pks = ids.join(",");
  return HTTP.patch(`${group}/${pks}/bookmark`, data);
};

export default {
  getAvailableFilterChoices,
  getFilterChoices,
  getMetadata,
  getSettings,
  loadBrowserPage,
  setGroupBookmarks,
};
