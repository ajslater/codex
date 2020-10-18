import API from "@/api/v2/comic";
import FORM_CHOICES from "@/choices/readerChoices";
import router from "@/router";

const NULL_READER_SETTINGS = {
  fitTo: null,
  twoPages: null,
};

const getGlobalFitToDefault = () => {
  // Default to different settings for different screen sizes;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0
  );
  let fitTo;
  if (vw > 600) {
    fitTo = "HEIGHT";
  } else {
    fitTo = "WIDTH";
  }
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
    local: {
      fitTo: null,
      twoPages: null,
    },
  },
  routes: {
    current: {
      pk: undefined,
      page: undefined,
    },
    prev: undefined,
    next: undefined,
    prevBook: undefined,
    nextBook: undefined,
  },
  formChoices: {
    fitTo: FORM_CHOICES.fitTo,
  },
};

const getters = {
  computedSettings: (state) => {
    // Use the global settings keys as a default for local bookmark settings
    // Fall back to device size defaults.
    const computedSettings = {};
    Object.keys(state.settings.globl).forEach(function (key) {
      if (state.settings.local[key] !== null) {
        computedSettings[key] = state.settings.local[key];
      } else {
        computedSettings[key] = state.settings.globl[key];
      }
    });
    return computedSettings;
  },
};

const mutations = {
  setCurrentRoute(state, route) {
    state.routes.current = route;
  },
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
    state.title.issue = parseFloat(data.title.issue);
    state.title.issueCount = data.title.issueCount;
    state.maxPage = data.maxPage;
    state.settings = data.settings;
    state.routes.prevBook = data.routes.prevBook;
    state.routes.nextBook = data.routes.nextBook;
    state.routes.current.pk = data.pk;
  },
  setCurrentPrevRoute(state, { page, previousPage }) {
    state.routes.current.page = page;
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
  newComicRouteParams
) => {
  let newParams;
  if (condition) {
    newParams = {
      pk: routeParams.pk,
      page: routeParams.page + increment,
    };
  } else if (newComicRouteParams) {
    newParams = newComicRouteParams;
  } else {
    newParams = null;
  }
  return newParams;
};

const getPreviousRouteParams = (routeParams, state) => {
  const condition = routeParams.page > 0;
  const increment = -1;
  return getRouteParams(
    condition,
    routeParams,
    increment,
    state.routes.prevBook
  );
};

const getNextRouteParams = (routeParams, state) => {
  const twoPages = getters.computedSettings(state).twoPages;
  const increment = twoPages ? 2 : 1;
  const condition = routeParams.page + increment <= state.maxPage;
  return getRouteParams(
    condition,
    routeParams,
    increment,
    state.routes.nextBook
  );
};

const handleBookChangedResult = ({ dispatch, commit }, route, info) => {
  info.pk = +route.pk;
  commit("setBookInfo", info);
  dispatch("routeChanged", route);
};

const actions = {
  async readerOpened({ dispatch, commit }, route) {
    commit("setCurrentRoute", route);
    const response = await API.getComicOpened(route.pk);
    handleBookChangedResult({ dispatch, commit }, route, response.data);
  },
  async bookChanged({ dispatch, commit }, route) {
    const response = await API.getComicOpened(route.pk);
    handleBookChangedResult({ dispatch, commit }, route, response.data);
  },
  nextRouteChanged({ commit, state }, route) {
    const nextPage = getNextRouteParams(route, state);
    commit("setNextPage", nextPage);
  },
  routeChanged({ commit, state, dispatch }, route) {
    // Commit prev & next Pages to state.
    const previousPage = getPreviousRouteParams(route, state);
    commit("setCurrentPrevRoute", {
      page: route.page,
      previousPage,
    });
    dispatch("nextRouteChanged", route);

    // Set the bookmark
    API.setComicBookmark(route);
  },
  settingChangedLocal({ commit, state, dispatch }, data) {
    commit("setSettingLocal", data);
    API.setComicSettings({
      pk: state.routes.current.pk,
      data: state.settings.local,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      dispatch("nextRouteChanged", state.routes.current);
    }
  },
  settingChangedGlobal({ commit, state, dispatch }, data) {
    commit("setSettingGlobal", data);
    commit("setSettingLocal", NULL_READER_SETTINGS);
    API.setComicDefaultSettings({
      pk: state.routes.current.pk,
      data: state.settings.globl,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      dispatch("nextRouteChanged", state.routes.current);
    }
  },
  routeTo({ state }, routeParams) {
    if (routeParams === "next") {
      routeParams = state.routes.next;
    } else if (routeParams === "prev") {
      routeParams = state.routes.prev;
    } else if (!routeParams || !routeParams.pk || routeParams.page == null) {
      console.warn("Invalid route, not pushing:", routeParams);
      return;
    }
    if (routeParams.pk === state.routes.current.pk) {
      if (routeParams.page === state.routes.current.routeParams) {
        return;
      }
      if (routeParams.page > state.maxPage) {
        routeParams.maxPage = state.maxPage;
      }
    }
    if (routeParams.page < 0) {
      routeParams.page = 0;
    }
    router.push({
      name: "reader",
      params: routeParams,
    });
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
