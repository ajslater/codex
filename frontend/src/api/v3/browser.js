import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

const getAvailableFilterChoices = ({ group, pks }, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices_available`, { params });
};

const getFilterChoices = ({ group, pks }, fieldName, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/choices/${fieldName}`, { params });
};

const loadBrowserPage = ({ group, pks, page }, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/${page}`, { params });
};

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const mtime = Math.max(group.mtime, settings.mtime);
  const data = { ...settings };
  delete data.mtime;
  const params = serializeParams(data, mtime);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

const getSettings = () => {
  const params = serializeParams({});
  return HTTP.get("/r/settings", { params });
};

export default {
  getAvailableFilterChoices,
  getFilterChoices,
  getMetadata,
  getSettings,
  loadBrowserPage,
};
