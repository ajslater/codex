import { HTTP } from "./base";

// REST ENDPOINTS
//
const trimObject = (obj) => {
  // Remove empty and undefined objects because they're just the default.
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

const pruneParams = (data) => {
  const params = trimObject(data);
  if (params.autoquery === "") {
    delete params.autoquery;
  }
  return params;
};

const getBrowserChoices = ({ group, pk }, choice_type, data) => {
  const params = pruneParams(data);
  return HTTP.get(`/${group}/${pk}/choices/${choice_type}`, { params });
};

const loadBrowserPage = ({ group, pk, page }, data) => {
  const params = pruneParams(data);
  return HTTP.get(`/${group}/${pk}/${page}`, { params });
};

const getMetadata = ({ group, pk }, data) => {
  const params = pruneParams(data);
  return HTTP.get(`/${group}/${pk}/metadata`, { params });
};

const getSettings = () => {
  return HTTP.get("/r/settings");
};

const setGroupBookmarks = ({ group, pk }, data) => {
  return HTTP.patch(`${group}/${pk}/bookmark`, data);
};

export default {
  getBrowserChoices,
  loadBrowserPage,
  getMetadata,
  getSettings,
  setGroupBookmarks,
};
