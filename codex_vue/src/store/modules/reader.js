import API from "@/api/reader";
import FORM_CHOICES from "@/choices/readerChoices";

const state = {
  // book
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
  // routes
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

// actions
const getters = {
  computedSettings: (state) => {
    // use the global settings keys as a default for local bookmark settings
    const computedSettings = {};
    Object.keys(state.settings.globl).forEach(function (key) {
      if (
        state.settings.local[key] !== null &&
        state.settings.local[key] !== undefined
      ) {
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
    state.title = data.title;
    state.maxPage = data.maxPage;
    state.routes.current.pk = data.pk;
    state.routes.prevBook = data.prevComicPage;
    state.routes.nextBook = data.nextComicPage;
    state.settings = data.settings;
    document.title = data.title;
  },
  setPrevNextPage(state, { pageNumber, previousPage, nextPage }) {
    state.routes.current.pageNumber = pageNumber;
    state.routes.prev = previousPage;
    state.routes.next = nextPage;
  },
};

const getPage = (condition, route, increment, newComicRoute) => {
  let page = undefined;
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
  const increment = state.settings.twoPages ? 2 : 1;
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
    const response = await API.getComicReader(+route.pk);
    handleBookChangedResult({ dispatch, commit }, route, response.data);
  },
  async bookChanged({ dispatch, commit }, route) {
    const response = await API.getComicOpened(route.pk);
    handleBookChangedResult({ dispatch, commit }, route, response.data);
  },
  pageChanged({ commit, state }, route) {
    // Commit prev & next Pages to state.
    const previousPage = getPreviousPage(route, state);
    const nextPage = getNextPage(route, state);
    commit("setPrevNextPage", {
      pageNumber: route.pageNumber,
      previousPage,
      nextPage,
    });

    alterPrefetch(nextPage, state);

    // Set the bookmark
    API.setComicBookmark(route);
  },
  settingChangedLocal({ commit, state }, data) {
    commit("setSettingLocal", data);
    API.setComicSettings({
      pk: state.routes.current.pk,
      data: state.settings.local,
    });
  },
  settingChangedGlobal({ commit, state }, data) {
    commit("setSettingGlobal", data);
    API.setComicDefaultSettings(state.settings.global);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
