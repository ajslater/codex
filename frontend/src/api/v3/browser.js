import { serializeParams } from "@/stores/common";

import { HTTP } from "./base";

const JSON_KEYS = ["filters", "show"];
Object.freeze(JSON_KEYS);

const getAvailableFilterChoices = ({ group, pks }, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices_available`, { params });
};

const getFilterChoices = ({ group, pks }, fieldName, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices/${fieldName}`, { params });
};

const loadBrowserPage = ({ group, pks, page }, data, ts) => {
  const params = serializeParams(data, ts, JSON_KEYS);
  return HTTP.get(`/${group}/${pks}/${page}`, { params });
};

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const mtime = Math.max(group.mtime, settings.mtime);
  const data = { ...settings };
  delete data.mtime;
  const params = serializeParams(data, mtime, JSON_KEYS);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

const getSettings = (ts) => {
  const params = serializeParams({}, ts);
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
