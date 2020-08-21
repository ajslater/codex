import API from "@/api/reader";
import FORM_CHOICES from "@/choices/readerChoices";

const state = {
  title: "",
  maxPage: 0,
  settings: {
    globl: {
      fitTo: "WIDTH",
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
      pageNumber: undefined,
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
    // TODO make sure we save the computed settings
    const computedSettings = {};
    Object.keys(state.settings.globl).forEach(function (key) {
      if (state.settings.local[key] !== null) {
        computedSettings[key] = state.settings.local[key];
      } else if (key === "fitTo") {
        // Default to different settings for different screen sizes;
        const vw = Math.max(
          document.documentElement.clientWidth || 0,
          window.innerWidth || 0
        );
        if (vw > 600) {
          computedSettings[key] = "HEIGHT";
        } else {
          computedSettings[key] = "WIDTH";
        }
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
    state.title = data.title;
    state.maxPage = data.maxPage;
    state.settings = data.settings;
    state.routes.prevBook = data.routes.prevBook;
    state.routes.nextBook = data.routes.nextBook;
    state.routes.current.pk = data.pk;
    document.title = data.title;
  },
  setCurrentPrevPage(state, { pageNumber, previousPage }) {
    state.routes.current.pageNumber = pageNumber;
    state.routes.prev = previousPage;
  },
  setNextPage(state, nextPage) {
    state.routes.next = nextPage;
  },
};

// action helpers

const getPage = (condition, route, increment, newComicRoute) => {
  let page = null;
  if (condition) {
    page = {
      pk: route.pk,
      pageNumber: route.pageNumber + increment,
    };
  } else if (newComicRoute) {
    page = newComicRoute;
  }
  return page;
};

const getPreviousPage = (route, state) => {
  const condition = route.pageNumber > 0;
  const increment = -1;
  return getPage(condition, route, increment, state.routes.prevBook);
};

const getNextPage = (route, state) => {
  const twoPages = getters.computedSettings(state).twoPages;
  const increment = twoPages ? 2 : 1;
  const condition = route.pageNumber + increment <= state.maxPage;
  return getPage(condition, route, increment, state.routes.nextBook);
};

const alterPrefetch = (nextPage, state) => {
  let nextPageHref = "";
  let next2PageHref = "";
  if (nextPage) {
    nextPageHref = API.getComicPageSource(nextPage);

    if (state.settings.twoPages && nextPage.pageNumber < state.maxPage) {
      const next2Page = {
        pk: nextPage.pk,
        pageNumber: nextPage.pageNumber + 1,
      };
      next2PageHref = API.getComicPageSource(next2Page);
    }
  }
  const nextPagePre = document.querySelector("#nextPage");
  nextPagePre["href"] = nextPageHref;
  const next2PagePre = document.querySelector("#next2Page");
  next2PagePre["href"] = next2PageHref;
};

const handleBookChangedResult = ({ dispatch, commit }, route, info) => {
  info.pk = +route.pk;
  commit("setBookInfo", info);
  dispatch("pageChanged", route);
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
  nextPageChanged({ commit, state }, route) {
    const nextPage = getNextPage(route, state);
    commit("setNextPage", nextPage);
    alterPrefetch(nextPage, state);
  },
  pageChanged({ commit, state, dispatch }, route) {
    // Commit prev & next Pages to state.
    const previousPage = getPreviousPage(route, state);
    commit("setCurrentPrevPage", {
      pageNumber: route.pageNumber,
      previousPage,
    });
    dispatch("nextPageChanged", route);

    // Set the bookmark
    API.setComicBookmark(route);
  },
  settingChangedLocal({ commit, state, dispatch }, { data, route }) {
    commit("setSettingLocal", data);
    API.setComicSettings({
      pk: state.routes.current.pk,
      data: state.settings.local,
    });
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      dispatch("nextPageChanged", route);
    }
  },
  settingChangedGlobal({ commit, state, dispatch }, { data, route }) {
    commit("setSettingGlobal", data);
    API.setComicDefaultSettings(state.settings.global);
    if (Object.prototype.hasOwnProperty.call(data, "twoPages")) {
      dispatch("nextPageChanged", route);
    }
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
