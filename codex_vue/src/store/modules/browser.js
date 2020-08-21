import API from "@/api/browser";
import router from "@/router";

const GROUPS = "rpisvf";
const REVALIDATE_KEYS = ["rootGroup", "show"];
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
import { settingsGroupChoices } from "@/choices/browserChoices";

let show = {};
for (let choice of settingsGroupChoices) {
  show[choice.value] = show.default === true;
}
const state = {
  routes: {
    current: undefined,
    up: undefined,
  },
  settings: {
    // set by user
    bookmarkFilter: undefined,
    decadeFilter: undefined,
    charactersFilter: undefined,
    rootGroup: undefined,
    sortBy: undefined,
    sortReverse: undefined,
    show,
  },
  formChoices: {
    // determined by api
    decadeFilterChoices: [],
    charactersFilterChoices: [],
    show: {
      enableFolderView: true,
    },
  },
  browseTitle: "",
  containerList: [],
  comicList: [],
  adminURL: "",
};

const getters = {};

const mutations = {
  setAdminURL(state, adminURL) {
    state.adminURL = adminURL;
  },
  setBrowseRoute(state, route) {
    state.routes.current = route;
  },
  setSettings(state, data) {
    if (data.show) {
      for (let [key, value] of Object.entries(data.show)) {
        state.settings.show[key] = value;
      }
      delete data["show"];
    }
    for (let [key, value] of Object.entries(data)) {
      state.settings[key] = value;
    }
  },
  setBrowseData(state, data) {
    const show = {
      enableFolderView: data.formChoices.enableFolderView,
    };
    delete data.formChoices["enableFolderView"];
    state.formChoices = data.formChoices;
    state.formChoices.show = show;

    state.browseTitle = data.browseTitle;
    state.routes.up = data.upRoute;
    state.containerList = data.containerList;
    state.comicList = data.comicList;
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
  console.log("isGroupChildOfRootGroup", isGroupChildOfRootGroup);
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
        commit("setAdminURL", data.adminURL);
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
  async markRead({ dispatch, state }, data) {
    await API.setMarkRead(data);
    if (state.settings.bookmarkFilter !== "ALL") {
      // Reget the objects if we're filtering on this change.
      dispatch("getBrowseObjects");
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
