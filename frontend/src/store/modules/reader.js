import API from "@/api/v2/comic";
import CHOICES from "@/choices";
import router from "@/router";

const NULL_READER_SETTINGS = {
  fitTo: undefined,
  twoPages: undefined,
};

const getGlobalFitToDefault = () => {
  // Default to different settings for different screen sizes;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0
  );
  let fitTo;
  fitTo = vw > 600 ? "HEIGHT" : "WIDTH";
  return fitTo;
};

const state = {
  title: {
    seriesName: "",
    volumeName: "",
    issue: 0,
    issueCount: undefined,
  },
  maxPage: 0,
  settings: {
    globl: {
      fitTo: getGlobalFitToDefault(),
      twoPages: false,
    },
    local: JSON.parse(JSON.stringify(NULL_READER_SETTINGS)),
  },
  routes: {
    prev: undefined,
    next: undefined,
    prevBook: undefined,
    nextBook: undefined,
  },
  formChoices: {
    fitTo: CHOICES.reader.fitTo,
  },
  browserRoute: CHOICES.browser.route,
};

const getters = {
  computedSettings: (state) => {
    // Use the global settings keys as a default for local bookmark settings
    // Fall back to device size defaults.
    const computedSettings = {};
    for (const key in state.settings.globl) {
      if (
        state.settings.local[key] !== null &&
        state.settings.local[key] !== undefined
      ) {
        computedSettings[key] = state.settings.local[key];
      } else {
        computedSettings[key] = state.settings.globl[key];
      }
    }
    return computedSettings;
  },
};

const mutations = {
  setReaderChoices(state, data) {
    state.fitToChoices = data.fitToChoices;
  },
  setSettingLocal(state, settings) {
    state.settings.local = Object.assign(state.settings.local, settings);
  },
  setSettingGlobal(state, settings) {
    state.settings.globl = Object.assign(state.settings.globl, settings);
  },
  setBookInfo(state, data) {
    state.title.seriesName = data.title.seriesName;
    state.title.volumeName = data.title.volumeName;
    state.title.issue = Number.parseFloat(data.title.issue);
    state.title.issueCount = data.title.issueCount;
    state.maxPage = data.maxPage;
    state.routes.prevBook = data.routes.prevBook;
    state.routes.nextBook = data.routes.nextBook;
    state.browserRoute = data.browserRoute;
  },
  setBrowserRoute(state, value) {
    state.browserRoute = value;
  },
  setSettings(state, data) {
    state.settings = data;
  },
  setPrevRoute(state, { previousPage }) {
    state.routes.prev = previousPage;
  },
  setNextPage(state, nextPage) {
    state.routes.next = nextPage;
  },
};

// action helpers

const getRouteParams = (
  condition,
  routeParams,
  increment,
  comicRouteParams
) => {
  let params;
  if (condition) {
    params = {
      pk: Number(routeParams.pk),
      page: Number(routeParams.page) + increment,
    };
  } else if (comicRouteParams) {
    params = comicRouteParams;
  }
  return params;
};

const getPreviousRouteParams = (state) => {
  const routeParams = router.currentRoute.params;
  const condition = Number(routeParams.page) > 0;
  const increment = -1;
  return getRouteParams(
    condition,
    routeParams,
    increment,
    state.routes.prevBook
  );
};

const getNextRouteParams = (state) => {
  const twoPages = getters.computedSettings(state).twoPages;
  const increment = twoPages ? 2 : 1;
  const routeParams = router.currentRoute.params;
  const condition = Number(routeParams.page) + increment <= state.maxPage;
  return getRouteParams(
    condition,
    routeParams,
    increment,
    state.routes.nextBook
  );
};

const actions = {
  routerPush(_, route) {
    router.push(route).catch((error) => {
      console.debug(error);
    });
  },
  async fetchComicSettings({ commit, dispatch }, info) {
    return API.getComicSettings(router.currentRoute.params.pk)
      .then((response) => {
        const data = response.data;
        commit("setBookInfo", info);
        commit("setSettings", data);
        return dispatch("routeChanged");
      })
      .catch((error) => {
        return console.error(error);
      });
  },
  async bookChanged({ dispatch }) {
    await API.getComicOpened(router.currentRoute.params.pk)
      .then((response) => {
        const info = response.data;
        return dispatch("fetchComicSettings", info);
      })
      .catch((error) => {
        if ([303, 404].includes(error.response.status)) {
          const data = error.response.data;
          console.debug(`redirect: ${data.reason}`);
          const route = { name: "browser", params: data.route };
          return dispatch("routerPush", route);
        } else {
          console.error(error);
        }
      });
  },
  nextRouteChanged({ commit, state }) {
    const nextPage = getNextRouteParams(state);
    commit("setNextPage", nextPage);
  },
  routeChanged({ commit, state, dispatch }) {
    // Commit prev & next Pages to state.
    const previousPage = getPreviousRouteParams(state);
    commit("setPrevRoute", { previousPage });
    dispatch("nextRouteChanged");

    // Set the bookmark
    API.setComicBookmark(router.currentRoute.params);
  },
  settingChangedLocal({ commit, state, dispatch }, data) {
    commit("setSettingLocal", data);
    API.setComicSettings({
      pk: router.currentRoute.params.pk,
      data: state.settings.local,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      dispatch("nextRouteChanged");
    }
  },
  settingsDialogClear({ dispatch }) {
    dispatch("reader/settingChangedLocal", NULL_READER_SETTINGS);
  },
  settingChangedGlobal({ commit, state, dispatch }, data) {
    commit("setSettingGlobal", data);
    commit("setSettingLocal", NULL_READER_SETTINGS);
    API.setComicDefaultSettings({
      pk: router.currentRoute.params.pk,
      data: state.settings.globl,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      dispatch("nextRouteChanged");
    }
  },
  routeTo({ dispatch, state }, routeParams) {
    // Construct route
    let finalRouteParams;
    if (routeParams === "next") {
      finalRouteParams = state.routes.next;
    } else if (routeParams === "prev") {
      finalRouteParams = state.routes.prev;
    } else {
      finalRouteParams = routeParams;
    }

    // Validate route
    if (finalRouteParams.pk === router.currentRoute.params.pk) {
      if (finalRouteParams.page > state.maxPage) {
        finalRouteParams.page = state.maxPage;
        console.warn("Tried to navigate past the end of the book.");
      } else if (finalRouteParams.page < 0) {
        finalRouteParams.page = 0;
        console.warn("Tried to navigate before the beginning of the book.");
      }
    }
    const route = { name: "reader", params: finalRouteParams };
    return dispatch("routerPush", route);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
