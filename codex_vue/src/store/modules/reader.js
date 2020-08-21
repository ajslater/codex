import API from "@/api/reader";

const state = {
  // book
  title: "",
  maxPage: 0,
  settings: {
    fitTo: "HEIGHT",
    twoPages: false,
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
};

// actions
const getters = {};

const mutations = {
  setCurrentRoute(state, route) {
    state.routes.current = route;
  },
  setReaderChoices(state, data) {
    state.fitToChoices = data.fitToChoices;
  },
  setReaderSettings(state, data) {
    state.settings = Object.assign(state.settings, data);
  },
  setBookInfo(state, data) {
    state.title = data.title;
    state.maxPage = data.maxPage;
    state.routes.current.pk = data.pk;
    state.routes.prevBook = data.prevComicPage;
    state.routes.nextBook = data.nextComicPage;
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
  commit("setReaderSettings", info.settings);
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
  settingChanged({ commit, state }, settings) {
    commit("setReaderSettings", settings);
    API.setComicSettings({ pk: state.routes.current.pk, data: state.settings });
  },
  defaultSettingsChanged({ state }) {
    API.setComicDefaultSettings(state.settings);
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
