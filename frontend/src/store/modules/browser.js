import API from "@/api/v1/browser";
import router from "@/router";

const GROUPS = "rpisvf";
const REVALIDATE_KEYS = ["rootGroup", "show"];
const DYNAMIC_FILTERS = ["decade", "characters"];
export const ROOT_GROUP_FLAGS = {
  r: ["settings", "p"],
  p: ["settings", "i"],
  i: ["settings", "s"],
  s: ["settings", "v"],
  f: ["formChoices", "enableFolderView"],
};
export const GROUP_FLAGS = {
  p: ["settings", "p"],
  i: ["settings", "i"],
  s: ["settings", "s"],
  v: ["settings", "v"],
  f: ["formChoices", "enableFolderView"],
};
import FORM_CHOICES from "@/choices/browserChoices";
const MIN_SCAN_WAIT = 5000;
const MAX_SCAN_WAIT = 10000;

let SETTINGS_SHOW_DEFAULTS = {};
for (let choice of FORM_CHOICES.settingsGroup) {
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
      decade: undefined,
      characters: undefined,
    },
    rootGroup: undefined,
    sortBy: undefined,
    sortReverse: undefined,
    show: SETTINGS_SHOW_DEFAULTS,
  },
  formChoices: {
    // determined by api
    bookmark: FORM_CHOICES.bookmarkFilter,
    decade: null,
    characters: null,
    sort: FORM_CHOICES.sort,
    settingsGroup: FORM_CHOICES.settingsGroup,
    show: {
      enableFolderView: true,
    },
  },
  browserTitle: {
    parentName: undefined,
    groupName: undefined,
    groupCount: undefined,
  },
  objList: [],
  filterMode: "base",
  browserPageLoaded: false,
  librariesExist: null,
  scanNotify: false,
  numPages: 1,
  versions: {
    installed: process.env.VUE_APP_PACKAGE_VERSION,
    latest: undefined,
  },
};

const isRootGroupEnabled = (state, rootGroup) => {
  if (rootGroup === "v") {
    return true;
  }
  const [key, flag] = ROOT_GROUP_FLAGS[rootGroup];
  return state[key].show[flag];
};

const getters = {
  rootGroupChoices: (state) => {
    const choices = [];
    for (let item of Object.values(FORM_CHOICES.rootGroup)) {
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
  setBrowserRoute(state, route) {
    state.routes.current = route;
  },
  setVersions(state, versions) {
    state.versions = versions;
  },
  setSettings(state, data) {
    if (!data) {
      console.warn("no settings data! ${data}");
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
    for (let key of DYNAMIC_FILTERS) {
      // Reset this every browse so the lazy loader knows to refresh it.
      state.formChoices[key] = null;
    }
    state.browserTitle = Object.freeze(data.browserTitle);
    state.routes.up = Object.freeze(data.upRoute);
    state.objList = Object.freeze(data.objList);
    state.numPages = data.numPages;
    state.librariesExist = data.librariesExist;
  },
  setBrowseChoice(state, data) {
    const key = data.key;
    delete data.key;
    state.formChoices[key] = Object.freeze(data);
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
  setScanNotify(state, data) {
    state.scanNotify = data.scanInProgress;
  },
};

const getValidRootGroup = (state, fromTop = false) => {
  /* Get a valid root group when we don't know what root group to get.
   * if fromTop is true, start looking from the currentRootGroup down.
   */

  // Check folder first because of its bottom position.
  // Only return it if its been explicitly selected.
  if (
    state.settings.rootGroup === "f" &&
    state.formChoices.show.enableFolderView
  ) {
    return "f";
  }
  // Look for the first valid root group starting from the top
  let atTop = false;
  for (let group of GROUPS) {
    if (fromTop) {
      if (group === state.settings.rootGroup) {
        atTop = true;
      }
      if (!atTop) {
        continue;
      }
    }
    if (isRootGroupEnabled(state, group)) {
      return group;
    }
  }
  // Volumes is the root group of last resort.
  return "v";
};

const topGroupRoute = (group) => {
  return {
    name: "browser",
    params: { group, pk: 0, page: 1 },
  };
};

const pushToRootGroupTop = ({ state, commit }) => {
  // Push to the top of a root group
  const group = getValidRootGroup(state, true);
  const route = topGroupRoute(group);
  commit("setSettings", { rootGroup: group });
  console.debug("push to", route);
  return router.push(route);
};

const handleBrowseError = ({ state, commit }, error) => {
  console.error("Browse", error);
  if (error.response.status == 403) {
    return pushToRootGroupTop({ state, commit });
  }
  console.error("Unhandled Browse error");
};
const validateRootGroup = (state) => {
  // Some root groups aren't allowed by the settings.
  let rootGroup = state.settings.rootGroup;
  if (!isRootGroupEnabled(state, rootGroup)) {
    rootGroup = getValidRootGroup(state, false);
    console.debug("new root group set to", rootGroup);
  }
  return rootGroup;
};

const isGroupEnabled = (state, group) => {
  // Are we allowed to view this group per the settings?
  if (group === state.settings.rootGroup) {
    return true;
  }
  const [key, flag] = GROUP_FLAGS[group];
  return state[key].show[flag];
};

const validateRoute = ({ state, commit }, route) => {
  // validate the route and push away if its bad.
  const group = route.group;
  const rootGroup = state.settings.rootGroup;

  const doPushToRootGroup =
    rootGroup !== group && [rootGroup, group].includes("f");
  const isGroupChildOfRootGroup =
    GROUPS.indexOf(group) >= GROUPS.indexOf(rootGroup);
  if (
    !doPushToRootGroup &&
    isGroupChildOfRootGroup &&
    isGroupEnabled(state, group)
  ) {
    return true;
  }
  console.debug("Route invalid. Fixing");
  pushToRootGroupTop({ state, commit });
  return false;
};

const validateState = ({ state, commit, dispatch }) => {
  const rootGroup = validateRootGroup(state);
  if (rootGroup !== state.settings.rootGroup) {
    dispatch("settingChanged", { rootGroup: rootGroup });
    return false;
  }
  if (validateRoute({ state, commit }, state.routes.current)) {
    return true;
  }
  return false;
};

const isNeedValidate = (changedData) => {
  const intersection = REVALIDATE_KEYS.filter((key) =>
    Object.keys(changedData).includes(key)
  );
  return Boolean(intersection.length);
};

const scanNotifyCheck = (commit, state) => {
  // polite client thundering herd control
  const wait = Math.floor(
    Math.random() * (MAX_SCAN_WAIT - MIN_SCAN_WAIT) + MIN_SCAN_WAIT
  );
  setTimeout(async () => {
    if (state.scanNotify === null) {
      // null is a special value that means it was manually dismissed.
      // won't be reset until there's a true push from the server.
      return;
    }
    await API.getScanInProgress()
      .then((response) => {
        const data = response.data;
        commit("setScanNotify", data);
        if (state.scanNotify) {
          return scanNotifyCheck(commit, state);
        }
        return null;
      })
      .catch((error) => {
        console.error(error);
        console.warn("scanNotifyCheck() Response", error.response);
      });
  }, wait);
};

const actions = {
  async browserOpened({ state, commit, dispatch }, route) {
    // Gets everything needed to open the component.
    commit("setBrowsePageLoaded", false);
    commit("setBrowserRoute", route);
    await API.getBrowserOpened(route)
      .then((response) => {
        const data = response.data;
        commit("setVersions", data.versions);
        commit("setSettings", data.settings);
        if (!validateState({ state, commit, dispatch })) {
          // will have dispatched to SetSetting if fails.
          return;
        }
        commit("setBrowsePageLoaded", true);
        return commit("setBrowserPage", data.browserPage);
      })
      .catch((error) => {
        if (
          error.response &&
          error.response.data &&
          error.response.data.group
        ) {
          const data = error.response.data;
          console.warn(data.message);
          console.warn("Valid group is", data.group);
          const route = topGroupRoute(data.group);
          dispatch("browserOpened", route.params);
        } else {
          console.error(error);
          console.warn("browserOpened response:", error.response);
        }
        return handleBrowseError({ state, commit }, error);
      });
  },
  settingChanged({ state, commit, dispatch }, changedData) {
    // Save settings to state and re-get the objects.
    commit("setSettings", changedData);
    if (
      isNeedValidate(changedData) &&
      !validateState({ state, commit, dispatch })
    ) {
      console.warn("NOT VALIDATED");
      return;
    }
    dispatch("getBrowserPage");
  },
  routeChanged({ state, commit, dispatch }, route) {
    // When the route changes, reget the objects for that route.
    if (!validateRoute({ state, commit }, route)) {
      console.warn("invalid route!", route);
      return;
    }
    commit("setBrowserRoute", route);
    dispatch("getBrowserPage");
  },
  async getBrowserPage({ commit, dispatch, state }) {
    // Get objects for the current route and setttings.
    if (!state.browserPageLoaded) {
      return dispatch("browserOpened", state.routes.current);
    }
    await API.getBrowserPage({
      route: state.routes.current,
      settings: state.settings,
    })
      .then((response) => {
        return commit("setBrowserPage", response.data);
      })
      .catch((error) => {
        return handleBrowseError({ state, commit }, error);
      });
  },
  async markRead({ dispatch }, data) {
    await API.setMarkRead(data);
    dispatch("getBrowserPage");
  },
  async setFilterMode({ commit, state }, { group, pk, mode }) {
    if (mode && mode !== "base" && state.formChoices[mode] == null) {
      await API.getBrowserChoices({ group, pk, choice_type: mode })
        .then((response) => {
          response.data.key = mode;
          return commit("setBrowseChoice", response.data);
        })
        .catch((error) => {
          console.error("ERROR", error);
          console.error("ERROR.RESPONSE", error.response);
          console.error("couldn't get choices for", mode);
        });
    }
    commit("setFilterMode", mode);
  },
  clearFilters({ commit, dispatch, getters }) {
    commit("clearFilters", getters.filterNames);
    dispatch("getBrowserPage");
  },
  scanNotify({ commit, state }, value) {
    commit("setScanNotify", { scanInProgress: value });
    if (value !== null) {
      scanNotifyCheck(commit, state);
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
