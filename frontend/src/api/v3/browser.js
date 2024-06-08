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

const getBrowserPage = ({ group, pks, page }, data, ts) => {
  const params = serializeParams(data, ts);
  return HTTP.get(`/${group}/${pks}/${page}`, { params });
};

export const getCoverSrc = ({ group, pks }, data, ts) => {
  const base = window.CODEX.API_V3_PATH;
  const pks_str = pks.join(",");
  const params = serializeParams(data, ts);
  const queryString = new URLSearchParams(params).toString();
  return `${base}${group}/${pks_str}/cover.webp?${queryString}`;
};

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const mtime = Math.max(group.mtime, settings.mtime);
  const data = { ...settings };
  delete data.mtime;
  const params = serializeParams(data, mtime);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

const getSettings = (only) => {
  const data = only ? { only } : {};
  const params = serializeParams(data);
  return HTTP.get("/r/settings", { params });
};

const updateSettings = (settings) => {
  const params = serializeParams(settings);
  return HTTP.patch("/r/settings", { params });
};

export default {
  getAvailableFilterChoices,
  getCoverSrc,
  getFilterChoices,
  getMetadata,
  getSettings,
  getBrowserPage,
  updateSettings,
};
