import { ajax } from "./base";

// REST ENDPOINTS

const getBrowserOpened = ({ group, pk, page }, ts) => {
  return ajax("get", `/${group}/${pk}/${page}?ts=${ts}`);
};

const getBrowserPage = ({ route, settings, ts }) => {
  const { group, pk, page } = route;
  return ajax("put", `/${group}/${pk}/${page}?ts=${ts}`, settings);
};

const getBrowserChoices = ({ group, pk, choice_type, ts }) => {
  return ajax("get", `/${group}/${pk}/choices/${choice_type}?ts=${ts}`);
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
