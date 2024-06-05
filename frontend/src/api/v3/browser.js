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

const DYNAMIC_COVER_KEYS = ["orderBy", "orderReverse", "filters"];
const COVER_KEYS = ["dynamicCovers", "customCovers"];
// TODO freeze
export const getCoverSrc = ({ group, pks }, data, ts) => {
  const base = window.CODEX.API_V3_PATH;
  const pks_str = pks.join(",");
  const usedData = {};
  if (group != "c") {
    for (const [key, value] of Object.entries(data)) {
      if (
        COVER_KEYS.includes(key) ||
        (data.dynamicCovers && DYNAMIC_COVER_KEYS.includes(key))
      ) {
        usedData[key] = value;
      }
    }
  }
  const params = serializeParams(usedData, ts);
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

const getSettings = () => {
  const params = serializeParams({});
  return HTTP.get("/r/settings", { params });
};

export default {
  getAvailableFilterChoices,
  getCoverSrc,
  getFilterChoices,
  getMetadata,
  getSettings,
  loadBrowserPage,
};
