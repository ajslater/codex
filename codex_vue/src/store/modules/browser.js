import API from "@/api/browser";
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
    decade: [],
    characters: [],
    sort: FORM_CHOICES.sort,
    settingsGroup: FORM_CHOICES.settingsGroup,
    show: {
      enableFolderView: true,
    },
  },
  browseTitle: "",
  containerList: [],
  comicList: [],
  filterMode: "base",
  librariesExist: false,
};

const getters = {
  rootGroupChoices: (state) => {
    const choices = [];
    for (let item of Object.values(FORM_CHOICES.rootGroup)) {
      const [key, flag] = ROOT_GROUP_FLAGS[item.value];
      const enable = state[key].show[flag];
      if (enable) {
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
  setBrowseRoute(state, route) {
    state.routes.current = route;
  },
  setLibrariesExist(state, value) {
    state.librariesExist = value;
  },
  setSettings(state, data) {
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
  setBrowseData(state, data) {
    state.formChoices.show = {
      enableFolderView: data.formChoices.enableFolderView,
    };
    for (let key of DYNAMIC_FILTERS) {
      state.formChoices[key] = data.formChoices[key];
    }
    state.browseTitle = data.browseTitle;
    state.routes.up = data.upRoute;
    state.containerList = data.containerList;
    state.comicList = data.comicList;
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
};

const pushToRootGroupTop = ({ state, commit }) => {
  // Push to the top of a root group
  const group = getValidRootGroup(state);
  const route = {
    name: "browser",
    params: { group, pk: 0 },
  };
  commit("setSettings", { rootGroup: group });
  console.debug("push to", route);
  return router.push(route);
};

const getValidRootGroup = (state) => {
  // do folder first because of its bottom position.
  if (
    state.settings.rootGroup === "f" &&
    state.formChoices.show.enableFolderView
  ) {
    return state.settings.rootGroup;
  }
  for (let [group, [key, flag]] of Object.entries(ROOT_GROUP_FLAGS)) {
    if (state[key].show[flag]) {
      return group;
    }
  }
  return "r";
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
  const [key, flag] = ROOT_GROUP_FLAGS[rootGroup];
  const enabled = state[key].show[flag];
  if (!enabled) {
    rootGroup = getValidRootGroup(state);
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

const actions = {
  async browseOpened({ state, commit, dispatch }, route) {
    // Gets everything needed to open the component.
    document.title = "Codex Browser";
    commit("setBrowseRoute", route);
    await API.getBrowseOpened(route)
      .then((response) => {
        const data = response.data;
        commit("setLibrariesExist", data.librariesExist);
        commit("setSettings", data.settings);
        if (!validateState({ state, commit, dispatch })) {
          // will have dispatched to SetSetting if fails.
          return;
        }
        return commit("setBrowseData", data.browseList);
      })
      .catch((error) => {
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
      return;
    }
    dispatch("getBrowseObjects");
  },
  routeChanged({ state, commit, dispatch }, route) {
    // When the route changes, reget the objects for that route.
    if (!validateRoute({ state, commit }, route)) {
      return;
    }
    commit("setBrowseRoute", route);
    dispatch("getBrowseObjects");
  },
  async getBrowseObjects({ commit, state }) {
    // Get objects for the current route and setttings.
    await API.getBrowseObjects({
      group: state.routes.current.group,
      pk: state.routes.current.pk,
      settings: state.settings,
    })
      .then((response) => {
        return commit("setBrowseData", response.data);
      })
      .catch((error) => {
        return handleBrowseError({ state, commit }, error);
      });
  },
  async markRead({ dispatch }, data) {
    await API.setMarkRead(data);
    dispatch("getBrowseObjects");
  },
  setFilterMode({ commit }, mode) {
    commit("setFilterMode", mode);
  },
  clearFilters({ commit, dispatch, getters }) {
    commit("clearFilters", getters.filterNames);
    dispatch("getBrowseObjects");
  },
};

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
};
