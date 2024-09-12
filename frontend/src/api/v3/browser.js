import deepClone from "deep-clone";

import { serializeParams } from "@/api/v3/common";

import { HTTP } from "./base";

const getBrowserHrefPath = ({ group, pks, query, ts }) => {
  const params = serializeParams(query, ts);
  const queryString = new URLSearchParams(params).toString();
  const pkList = pks.join(",");
  return { hrefPath: `${group}/${pkList}`, queryString };
};

export const getBrowserHref = ({ group, pks, query }) => {
  const base = window.CODEX.APP_PATH;
  const { hrefPath, queryString } = getBrowserHrefPath({
    group,
    pks,
    query,
  });
  return `${base}${hrefPath}/1?${queryString}`;
};

export const getCoverSrc = ({ group, pks }, data, ts) => {
  const base = window.CODEX.API_V3_PATH;
  const { hrefPath, queryString } = getBrowserHrefPath({
    group,
    pks,
    query: data,
    ts,
  });
  return `${base}${hrefPath}/cover.webp?${queryString}`;
};

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

const getMetadata = ({ group, pks }, settings) => {
  const pkList = pks.join(",");
  const mtime = Math.max(group.mtime, settings.mtime);
  const data = deepClone(settings);
  delete data.mtime;
  const params = serializeParams(data, mtime);
  return HTTP.get(`/${group}/${pkList}/metadata`, { params });
};

const getSettings = (data) => {
  const params = serializeParams(data);
  return HTTP.get("/r/settings", { params });
};

const updateSettings = (settings) => {
  return HTTP.patch("/r/settings", settings);
};

export default {
  getAvailableFilterChoices,
  getBrowserHref,
  getCoverSrc,
  getFilterChoices,
  getMetadata,
  getSettings,
  getBrowserPage,
  updateSettings,
};
