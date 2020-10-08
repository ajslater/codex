import { ajax, API_PREFIX, ROOT_PATH } from "./base";

export const BROWSE_BASE = "/browse";

// REST ENDPOINTS

const getBrowserOpened = ({ group, pk, page }) => {
  return ajax("get", `${BROWSE_BASE}/${group}/${pk}/${page}`);
};

const getBrowserPage = ({ route, settings }) => {
  const { group, pk, page } = route;
  return ajax("put", `${BROWSE_BASE}/${group}/${pk}/${page}`, settings);
};

const getBrowserChoices = ({ group, pk, choice_type }) => {
  return ajax("get", `${BROWSE_BASE}/${group}/${pk}/choices/${choice_type}`);
};

const setMarkRead = ({ group, pk, finished }) => {
  return ajax("patch", `${BROWSE_BASE}/${group}/${pk}/mark_read`, {
    finished,
  });
};

export default {
  getBrowserOpened,
  getBrowserPage,
  getBrowserChoices,
  setMarkRead,
};
