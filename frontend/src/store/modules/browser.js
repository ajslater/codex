import API from "@/api/v2/group";
import CHOICES from "@/choices";
import router from "@/router";

const DYNAMIC_FILTERS = {
  characters: undefined,
  country: undefined,
  critical_rating: undefined,
  creators: undefined,
  decade: undefined,
  format: undefined,
  genres: undefined,
  language: undefined,
  locations: undefined,
  maturity_rating: undefined,
  read_ltr: undefined,
  series_groups: undefined,
  story_arcs: undefined,
  tags: undefined,
  teams: undefined,
  user_rating: undefined,
  year: undefined,
};
const GROUP_FLAGS = {
  p: ["settings", "p"],
  i: ["settings", "i"],
  s: ["settings", "s"],
  v: ["settings", "v"],
  f: ["formChoices", "enableFolderView"],
};

const SETTINGS_SHOW_DEFAULTS = {};
for (let choice of CHOICES.browser.settingsGroup) {
  SETTINGS_SHOW_DEFAULTS[choice.value] = choice.default === true;
}

const state = {
  routes: {
    current: undefined,
    up: undefined,
  },
  settings: {
    // set by user
    filters: {
      bookmark: undefined,
      ...DYNAMIC_FILTERS,
    },
    autoquery: "",
    topGroup: undefined,
    orderBy: undefined,
    orderReverse: undefined,
    show: SETTINGS_SHOW_DEFAULTS,
  },
  formChoices: {
    bookmark: CHOICES.browser.bookmarkFilter, // static
    // determined by api
    ...DYNAMIC_FILTERS,
    orderBy: CHOICES.browser.orderBy, // static
    settingsGroup: CHOICES.browser.settingsGroup, // static
    show: {
      // determined by api
      enableFolderView: true,
    },
  },
  modelGroup: undefined,
  groupNames: CHOICES.browser.groupNames,
  browserTitle: {
    parentName: undefined,
    groupName: undefined,
    groupCount: undefined,
  },
  objList: [],
  filterMode: "base",
  browserPageLoaded: false,
  librariesExist: undefined,
  numPages: 1,
  versions: {
    installed: process.env.VUE_APP_PACKAGE_VERSION,
    latest: undefined,
  },
  queries: [],
};

const isRootGroupEnabled = (state, topGroup) => {
  if (topGroup === "c") {
    return true;
  }
  const [key, flag] = GROUP_FLAGS[topGroup];
  return state[key].show[flag];
};

const getters = {
  topGroupChoices: (state) => {
    const choices = [];
    for (const item of Object.values(CHOICES.browser.topGroup)) {
      if (isRootGroupEnabled(state, item.value)) {
        if (item.value === "f") {
          choices.push({ divider: true });
        }
        choices.push(item);
      }
    }
    return Object.values(choices);
  },
  filterNames: (state) => Object.keys(state.settings.filters).slice(1),
};

const mutations = {
  setBrowsePageLoaded(state, value) {
    state.browserPageLoaded = value;
  },
  setVersions(state, versions) {
    state.versions = versions;
  },
  setSettings(state, data) {
    if (!data) {
      console.warn("no settings data!");
      return;
    }
    for (let [key, value] of Object.entries(data)) {
      if (typeof state.settings[key] === "object") {
        for (let [sub_key, sub_value] of Object.entries(value)) {
          state.settings[key][sub_key] = sub_value;
        }
      } else {
        state.settings[key] = value;
      }
    }
  },
  setBrowserPage(state, data) {
    state.formChoices.show = {
      enableFolderView: data.formChoices.enableFolderView,
    };
    state.browserTitle = Object.freeze(data.browserTitle);
    state.modelGroup = Object.freeze(data.modelGroup);
    state.routes.up = Object.freeze(data.upRoute);
    state.objList = Object.freeze(data.objList);
    state.numPages = data.numPages;
    state.librariesExist = data.librariesExist;
    state.queries = data.queries;
  },
  setBrowseChoice(state, { choiceName, choices }) {
    state.formChoices[choiceName] = Object.freeze(choices);
  },
  setFilterMode(state, mode) {
    state.filterMode = mode;
  },
  clearFilters(state, filterNames) {
    state.filterMode = "base";
    state.settings.filters.bookmark = "ALL";
    for (let filterName of filterNames) {
      state.settings.filters[filterName] = [];
    }
  },
  clearAllFormChoicesExcept(state, keepChoiceName) {
    for (let choiceName of Object.keys(DYNAMIC_FILTERS)) {
      if (choiceName === keepChoiceName) {
        continue;
      }
      state.formChoices[choiceName] = undefined;
    }
  },
  setUpdateNotify(state, data) {
    state.updateNotify = data.updateInProgress;
  },
};

const handlePageError = (dispatch) => {
  return (error) => {
    if (error.response.status == 303) {
      const data = error.response.data;
      return dispatch("redirectRoute", data);
    } else {
      return console.error(error);
    }
  };
};

const actions = {
  redirectRoute({ commit, dispatch }, data) {
    commit("setSettings", data.settings);
    if (data.route) {
      router.push(data.route).catch((error) => {
        console.debug(error);
        dispatch("settingChanged", data);
      });
    }
  },
  routeToPage(_, page) {
    const route = {
      name: router.currentRoute.name,
      params: { ...router.currentRoute.params },
    };
    route.params.page = page;
    router.push(route).catch((error) => {
      console.debug(error);
    });
  },
  async browserOpened({ commit, dispatch }) {
    // Gets everything needed to open the component.
    commit("setBrowsePageLoaded", false);
    commit("clearAllFormChoicesExcept");
    await API.getBrowserOpened(router.currentRoute.params)
      .then((response) => {
        const data = response.data;
        commit("setSettings", data.settings);
        commit("setVersions", data.versions);
        commit("setBrowserPage", data.browserPage);
        return commit("setBrowsePageLoaded", true);
      })
      .catch(handlePageError(dispatch));
  },
  settingChanged({ commit, dispatch }, data) {
    // Save settings to state and re-get the objects.
    commit("setSettings", data);
    if ("filters" in data) {
      for (let filterName of Object.keys(data.filters)) {
        commit("clearAllFormChoicesExcept", filterName);
      }
    }
    dispatch("browserPageStale");
  },
  async browserPageStale({ commit, dispatch, state }) {
    // Get objects for the current route and settings.
    if (!state.browserPageLoaded) {
      console.debug("Browser not setup running open");
      return dispatch("browserOpened");
    }
    await API.getBrowserPage({
      route: router.currentRoute.params,
      settings: state.settings,
    })
      .then((response) => {
        const data = response.data;
        return commit("setBrowserPage", data);
      })
      .catch(handlePageError(dispatch));
  },
  async markedRead({ dispatch }, data) {
    await API.setMarkRead(data);
    dispatch("browserPageStale");
  },
  async filterModeChanged({ commit, state }, { group, pk, mode }) {
    if (mode && mode !== "base" && state.formChoices[mode] == undefined) {
      await API.getBrowserChoices({ group, pk, choice_type: mode })
        .then((response) => {
          response.data.key = mode;
          const payload = { choiceName: mode, choices: response.data };
          return commit("setBrowseChoice", payload);
        })
        .catch((error) => {
          console.error(error);
        });
    }
    commit("setFilterMode", mode);
  },
  filtersCleared({ commit, dispatch, getters }) {
    commit("clearFilters", getters.filterNames);
    commit("clearAllFormChoicesExcept");
    dispatch("browserPageStale");
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
