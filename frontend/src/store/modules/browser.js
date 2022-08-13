import API from "@/api/v2/group";
import CHOICES from "@/choices";
import router from "@/router";

const DYNAMIC_FILTERS = {
  ageRating: undefined,
  communityRating: undefined,
  characters: undefined,
  country: undefined,
  criticalRating: undefined,
  creators: undefined,
  decade: undefined,
  format: undefined,
  genres: undefined,
  language: undefined,
  locations: undefined,
  readLtr: undefined,
  seriesGroups: undefined,
  storyArcs: undefined,
  tags: undefined,
  teams: undefined,
  year: undefined,
};
Object.freeze(DYNAMIC_FILTERS);
export const NUMERIC_FILTERS = [
  "communityRating",
  "criticalRating",
  "decade",
  "year",
];
Object.freeze(NUMERIC_FILTERS);
const GROUP_FLAGS = {
  p: ["settings", "p"],
  i: ["settings", "i"],
  s: ["settings", "s"],
  v: ["settings", "v"],
  f: ["adminFlags", "enableFolderView"],
};
Object.freeze(GROUP_FLAGS);
const GROUPS_REVERSED = "cvsipr";
Object.freeze(GROUPS_REVERSED);
const SETTINGS_SHOW_DEFAULTS = {};
for (let choice of CHOICES.browser.settingsGroup) {
  SETTINGS_SHOW_DEFAULTS[choice.value] = choice.default === true;
}
Object.freeze(SETTINGS_SHOW_DEFAULTS);
const IS_OPEN_TO_SEE = "auth/isOpenToSee";
Object.freeze(IS_OPEN_TO_SEE);

const state = {
  coversTimestamp: 0,
  browseTimestamp: Date.now(),
  routes: {
    up: undefined,
    last: undefined,
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
    show: { ...SETTINGS_SHOW_DEFAULTS },
  },
  isSettingsDrawerOpen: false,
  formChoices: {
    bookmark: CHOICES.browser.bookmarkFilter, // static
    // determined by api
    ...DYNAMIC_FILTERS,
    settingsGroup: CHOICES.browser.settingsGroup, // static
  },
  adminFlags: {
    // determined by api
    enableFolderView: undefined,
  },
  modelGroup: undefined,
  groupNames: CHOICES.browser.groupNames,
  browserTitle: {
    parentName: undefined,
    groupName: undefined,
    groupCount: undefined,
  },
  objList: [],
  zeroPad: 0,
  filterMode: "base",
  browserPageLoaded: false,
  librariesExist: undefined,
  numPages: 1,
  versions: {
    // XXX not part of browser anymore
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
  const root = state[key];
  return topGroup === "f" ? root[flag] : root.show[flag];
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
  orderByChoices: (state) => {
    const choices = [];
    for (const item of Object.values(CHOICES.browser.orderBy)) {
      if (item.value === "path") {
        if (state.adminFlags.enableFolderView) {
          choices.push(item);
        }
      } else {
        choices.push(item);
      }
    }
    return Object.values(choices);
  },
};

const computeZeroPad = (issueMax) => {
  if (!issueMax || issueMax < 1) {
    return 1;
  }
  return Math.floor(Math.log10(issueMax)) + 1;
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
    state.adminFlags = Object.freeze(data.adminFlags);
    state.browserTitle = Object.freeze(data.browserTitle);
    state.modelGroup = Object.freeze(data.modelGroup);
    state.routes.up = Object.freeze(data.upRoute);
    state.objList = Object.freeze(data.objList);
    state.zeroPad = computeZeroPad(data.issueMax);
    state.numPages = data.numPages;
    state.librariesExist = data.librariesExist;
    state.queries = data.queries;
    state.coversTimestamp = data.coversTimestamp;
    state.routes.last = router.currentRoute.params;
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
  setBrowseTimestamp(state) {
    state.browseTimestamp = Date.now();
  },
  setIsSettingsDrawerOpen(state, value) {
    state.isSettingsDrawerOpen = value;
  },
  toggleSettingsDrawerOpen(state) {
    state.isSettingsDrawerOpen = !state.isSettingsDrawerOpen;
  },
};

const validateFirstSearch = ({ state }, data) => {
  // If first search redirect to lowest group and change order
  if (state.autoquery || !data.autoquery) {
    // Not first search, validated.
    return;
  }
  data.orderBy = "search_score";
  data.orderReverse = true;
  let lowestGroup = "r";
  for (const key of GROUPS_REVERSED) {
    const val = state.settings.show[key];
    if (val) {
      lowestGroup = key;
      break;
    }
  }
  const route = { params: { ...router.currentRoute.params } };
  route.params.group = lowestGroup;
  return { route, settings: {} };
};

const validateNewTopGroupIsParent = ({ state }, data) => {
  // If the top group changed and we're at the root group and the new top group is above the proper nav group
  if (
    router.currentRoute.params.group !== "r" ||
    !state.settings.topGroup ||
    GROUPS_REVERSED.indexOf(state.settings.topGroup) >
      GROUPS_REVERSED.indexOf(data.topGroup)
  ) {
    // All is well, validated.
    return;
  }
  const route = { params: { ...router.currentRoute.params } };

  let groupIndex = GROUPS_REVERSED.indexOf(state.settings.topGroup);
  const parentGroups = GROUPS_REVERSED.slice(groupIndex + 1);
  let jumpGroup;
  for (jumpGroup of parentGroups) {
    if (state.settings.show[jumpGroup]) {
      break;
    }
  }
  route.params.group = jumpGroup;
  return { route, settings: {} };
};

const clearChoicesAndResetFilterMode = ({ commit }, data) => {
  // clear choices and reset filter menu mode.
  if (!data.filters && !data.autoquery) {
    return;
  }
  let filterName;
  if (data.filters) {
    filterName = Object.keys(data.filters)[0];
  }
  commit("clearAllFormChoicesExcept", filterName);
  commit("setFilterMode", "base");
};

const validateSettings = ({ commit, state }, data) => {
  let redirect;
  redirect = validateFirstSearch({ state }, data);
  console.log({ redirect });
  redirect = validateNewTopGroupIsParent({ state }, data);
  console.log({ redirect });
  commit("setSettings", data);
  clearChoicesAndResetFilterMode({ commit }, data);
  commit("setBrowseTimestamp");
  return redirect;
};

const compareRouteParams = (a, b) => {
  return a.group === b.group && +a.pk === +b.pk && +a.page === +b.page;
};

const handlePageError = ({ commit, dispatch, state }) => {
  return (error) => {
    if (error.response.status == 303) {
      const data = error.response.data;
      const routesEqual = compareRouteParams(
        data.route.params,
        router.currentRoute.params
      );
      if (routesEqual) {
        dispatch("settingChanged", data.settings);
      } else {
        const redirect = validateSettings(
          { commit, dispatch, state },
          data.settings
        );
        if (redirect && !compareRouteParams(redirect, data.route)) {
          // ? i dunno if this is a good idea.
          data.route = redirect;
        }
        dispatch("redirectRoute", data);
      }
    } else {
      return console.error(error);
    }
  };
};

const actions = {
  redirectRoute(_, data) {
    if (data.route.params) {
      router.push(data.route).catch((error) => {
        console.debug(error);
        //dispatch("settingChanged", data.settings);
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
  async loadSettings({ commit, dispatch, rootGetters, state }) {
    if (!rootGetters[IS_OPEN_TO_SEE]) {
      return;
    }
    commit("setBrowsePageLoaded", false);
    commit("clearAllFormChoicesExcept");
    await API.getSettings()
      .then((response) => {
        const data = response.data;
        const redirect = validateSettings({ commit, dispatch, state }, data);
        console.log(redirect);

        commit("setBrowsePageLoaded", true);
        if (redirect) {
          return dispatch("redirectRoute", redirect);
        }
        return redirect;
      })
      .catch(handlePageError({ commit, dispatch, state }));
    dispatch("getBrowserPage");
  },
  settingChanged({ commit, dispatch, state }, data) {
    // Save settings to state and re-get the objects.
    const redirect = validateSettings({ commit, dispatch, state }, data);
    if (redirect) {
      return dispatch("redirectRoute", redirect);
    }
    dispatch("getBrowserPage");
  },
  async getBrowserPage({ commit, dispatch, rootGetters, state }) {
    // Get objects for the current route and settings.
    if (!rootGetters[IS_OPEN_TO_SEE]) {
      return;
    }
    if (!state.browserPageLoaded) {
      dispatch("loadSettings");
    }
    const queryParams = {
      ...state.settings,
      ts: state.browseTimestamp,
      // route: router.currentRoute.params,
      show: state.show,
    };
    await API.getBrowserOpened(router.currentRoute.params, queryParams)
      .then((response) => {
        const data = response.data;
        return commit("setBrowserPage", data.browserPage);
      })
      .catch(handlePageError({ commit, dispatch, state }));
  },
  async markedRead({ commit, dispatch, rootGetters }, data) {
    if (!rootGetters[IS_OPEN_TO_SEE]) {
      return;
    }
    await API.setMarkRead(data);
    commit("setBrowseTimestamp");
    dispatch("getBrowserPage");
  },
  async filterModeChanged({ commit, rootGetters, state }, { group, pk, mode }) {
    if (!rootGetters[IS_OPEN_TO_SEE]) {
      return;
    }
    if (!mode) {
      return;
    }
    if (mode !== "base" && state.formChoices[mode] == undefined) {
      await API.getBrowserChoices({
        group,
        pk,
        choice_type: mode,
        ts: state.browseTimestamp,
      })
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
    commit("setBrowseTimestamp");
    dispatch("getBrowserPage");
  },
  async getVersions({ commit }) {
    await API.getVersions()
      .then((response) => {
        const data = response.data;
        return commit("setVersions", data);
      })
      .catch((error) => {
        return console.error(error);
      });
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
  NUMERIC_FILTERS,
};
