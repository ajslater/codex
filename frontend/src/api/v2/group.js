import { ajax, HTTP } from "./base";

// REST ENDPOINTS
//
const trimObject = (obj) => {
  // Remove empty and undefined objects because they're just the default.
  const isArray = Array.isArray(obj);
  const result = isArray ? [] : {};
  for (const [key, val] of Object.entries(obj)) {
    if (val === undefined) {
      continue;
    }
    const isValObject = typeof val === "object";
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

const getBrowserOpened = ({ group, pk, page }, data) => {
  const params = trimObject(data);
  delete params.route;
  if (params.autoquery === "") {
    delete params.autoquery;
  }
  return HTTP.get(`/${group}/${pk}/${page}`, { params });
};

/*
const getBrowserPage = ({ route, settings, ts }) => {
  const { group, pk, page } = route;
  return ajax("put", `/${group}/${pk}/${page}?ts=${ts}`, settings);
};
*/

const getBrowserChoices = ({ group, pk, choice_type, ts }) => {
  return ajax("get", `/${group}/${pk}/choices/${choice_type}?ts=${ts}`);
};

const setMarkRead = ({ group, pk, finished }) => {
  return ajax("patch", `/${group}/${pk}/mark_read`, {
    finished,
  });
};

const getMetadata = ({ group, pk }, ts) => {
  return ajax("get", `/${group}/${pk}/metadata?ts=${ts}`);
};

const getSettings = () => {
  return ajax("get", "session/browser");
};

const getVersions = () => {
  return HTTP.get("/version");
};

export default {
  getBrowserOpened,
  // getBrowserPage,
  getBrowserChoices,
  setMarkRead,
  getMetadata,
  getSettings,
  getVersions,
};
