import { ajax } from "./base";

// REST ENDPOINTS

const getBrowserOpened = ({ group, pk, page }) => {
  return ajax("get", `/${group}/${pk}/${page}`);
};

const getBrowserPage = ({ route, settings }) => {
  const { group, pk, page } = route;
  return ajax("put", `/${group}/${pk}/${page}`, settings);
};

const getBrowserChoices = ({ group, pk, choice_type }) => {
  return ajax("get", `/${group}/${pk}/choices/${choice_type}`);
};

const setMarkRead = ({ group, pk, finished }) => {
  return ajax("patch", `/${group}/${pk}/mark_read`, {
    finished,
  });
};

const getMetadata = (group, pk) => {
  return ajax("get", `/${group}/${pk}/metadata`);
};

export default {
  getBrowserOpened,
  getBrowserPage,
  getBrowserChoices,
  setMarkRead,
  getMetadata,
};
