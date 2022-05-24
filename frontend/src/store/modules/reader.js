import API from "@/api/v2/comic";
import CHOICES from "@/choices";
import router from "@/router";

const NULL_READER_SETTINGS = {
  fitTo: undefined,
  twoPages: undefined,
};

const getGlobalFitToDefault = () => {
  // Big screens default to fit by HEIGHT, small to WIDTH;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0
  );
  return vw > 600 ? "HEIGHT" : "WIDTH";
};

const state = {
  comic: {
    fileFormat: undefined,
    issue: undefined,
    issueSuffix: "",
    issueCount: undefined,
    maxPage: 0,
    seriesName: "",
    volumeName: "",
  },
  timestamp: Date.now(),
  settings: {
    globl: {
      fitTo: getGlobalFitToDefault(),
      twoPages: false,
    },
    local: JSON.parse(JSON.stringify(NULL_READER_SETTINGS)),
    timestamp: Date.now(),
  },
  isSettingsDrawerOpen: false,
  routes: {
    prev: undefined,
    next: undefined,
    prevBook: undefined,
    nextBook: undefined,
  },
  bookChange: undefined,
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

// mutation helpers
//
const getRouteParams = (condition, routeParams, increment) => {
  return condition
    ? {
        pk: Number(routeParams.pk),
        page: Number(routeParams.page) + increment,
      }
    : false;
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
    state.browserRoute = data.browserRoute;
    state.comic = data.comic;
    // Only set prev/next book info do not clobber page routes.
    state.routes.prevBook = data.routes.prevBook;
    state.routes.nextBook = data.routes.nextBook;
    state.updatedAt = data.updatedAt;
  },
  setBrowserRoute(state, value) {
    state.browserRoute = value;
  },
  setSettings(state, data) {
    state.settings = data;
  },
  setPrevRoute(state) {
    const routeParams = router.currentRoute.params;
    const condition = Number(routeParams.page) > 0;
    const increment = -1;
    state.routes.prev = getRouteParams(condition, routeParams, increment);
  },
  setNextPage(state) {
    const routeParams = router.currentRoute.params;
    const twoPages = getters.computedSettings(state).twoPages;
    const increment = twoPages ? 2 : 1;
    const condition =
      Number(routeParams.page) + increment <= state.comic.maxPage;
    state.routes.next = getRouteParams(condition, routeParams, increment);
  },
  setTimestamp(state) {
    state.timestamp = Date.now();
  },
  setBookChange(state, val) {
    state.bookChange = val;
  },
  setIsSettingsDrawerOpen(state, value) {
    state.isSettingsDrawerOpen = value;
  },
  toggleSettingsDrawerOpen(state) {
    state.isSettingsDrawerOpen = !state.isSettingsDrawerOpen;
  },
};

// action
const isRouteBookChange = (state, direction) =>
  state.routes && !state.routes[direction] && state.routes[direction + "Book"];

const actions = {
  routerPush(_, route) {
    router.push(route).catch((error) => {
      console.debug(error);
    });
  },
  async fetchComicSettings({ commit, dispatch, state }, info) {
    return API.getComicSettings(
      router.currentRoute.params.pk,
      state.settings.timestamp
    )
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
  async bookChanged({ dispatch, state }) {
    await API.getComicOpened(router.currentRoute.params.pk, state.timestamp)
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
  routeChanged({ commit }) {
    commit("setPrevRoute");
    commit("setNextPage");
    commit("setBookChange"); // Reset!
    return API.setComicBookmark(router.currentRoute.params);
  },
  settingsChangedLocal({ commit, state }, data) {
    commit("setSettingLocal", data);
    API.setComicSettings({
      pk: router.currentRoute.params.pk,
      data: state.settings.local,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      commit("setNextPage");
    }
  },
  settingsDialogClear({ dispatch }) {
    dispatch("settingsChangedLocal", NULL_READER_SETTINGS);
  },
  settingsChangedGlobal({ commit, state }, data) {
    commit("setSettingGlobal", data);
    commit("setSettingLocal", NULL_READER_SETTINGS);
    API.setComicDefaultSettings({
      pk: router.currentRoute.params.pk,
      data: state.settings.globl,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      commit("setNextPage");
    }
  },
  setBookChangeFlag({ commit, state }, direction) {
    if (!direction) {
      commit("setBookChange");
    } else if (isRouteBookChange(state, direction)) {
      commit("setBookChange", direction);
    }
  },
  routeTo({ dispatch }, routeParams) {
    // Validate route
    if (routeParams.pk === router.currentRoute.params.pk) {
      if (routeParams.page > state.comic.maxPage) {
        routeParams.page = state.comic.maxPage;
        console.warn("Tried to navigate past the end of the book.");
      } else if (routeParams.page < 0) {
        routeParams.page = 0;
        console.warn("Tried to navigate before the beginning of the book.");
      }
    }
    const route = { name: "reader", params: routeParams };
    return dispatch("routerPush", route);
  },
  routeToDirection({ dispatch, state }, direction) {
    if (isRouteBookChange(state, direction) && state.bookChange !== direction) {
      // Block book change routes unless the book change flag is set.
      dispatch("setBookChangeFlag", direction);
      return;
    }
    // Get real route
    const finalRouteParams = state.routes[direction];

    dispatch("routeTo", finalRouteParams);
  },
  routeToPage({ dispatch }, page) {
    const params = { pk: Number(router.currentRoute.params.pk), page };
    dispatch("routeTo", params);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
