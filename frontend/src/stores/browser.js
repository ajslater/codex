import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import CHOICES from "@/choices";
import router from "@/router";
import { useAuthStore } from "@/stores/auth";

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
const GROUPS_REVERSED = "cvsipr";
Object.freeze(GROUPS_REVERSED);
const SETTINGS_SHOW_DEFAULTS = {};
for (let choice of CHOICES.browser.settingsGroup) {
  SETTINGS_SHOW_DEFAULTS[choice.value] = choice.default === true;
}
Object.freeze(SETTINGS_SHOW_DEFAULTS);

const isRootGroupEnabled = function (state, topGroup) {
  return topGroup === "c" || topGroup === "f"
    ? state.page.adminFlags.enableFolderView
    : state.settings.show[topGroup];
};

const getZeroPad = function (issueMax) {
  return !issueMax || issueMax < 1 ? 1 : Math.floor(Math.log10(issueMax)) + 1;
};

const clearAllFormChoicesExcept = function (state, keepChoiceName) {
  for (let choiceName of Object.keys(DYNAMIC_FILTERS)) {
    if (choiceName === keepChoiceName) {
      continue;
    }
    state.choices[choiceName] = undefined;
  }
};

const validateFirstSearch = function (state, data) {
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
  if (router.currentRoute.params.group === lowestGroup) {
    return;
  }
  const route = { params: { ...router.currentRoute.params } };
  route.params.group = lowestGroup;
  return route;
};

const validateNewTopGroupIsParent = function (state, data, redirect) {
  // If the top group changed and we're at the root group and the new top group is above the proper nav group
  const referenceRoute = redirect || router.currentRoute;
  if (
    referenceRoute.params.group !== "r" ||
    !state.settings.topGroup ||
    GROUPS_REVERSED.indexOf(state.settings.topGroup) >=
      GROUPS_REVERSED.indexOf(data.topGroup)
  ) {
    // All is well, validated.
    return redirect;
  }
  const route = { params: { ...referenceRoute.params } };

  let groupIndex = GROUPS_REVERSED.indexOf(state.settings.topGroup);
  const parentGroups = GROUPS_REVERSED.slice(groupIndex + 1);
  let jumpGroup;
  for (jumpGroup of parentGroups) {
    if (state.settings.show[jumpGroup]) {
      break;
    }
  }
  route.params.group = jumpGroup;
  return route;
};

const mutateSettings = function (store, data) {
  store.$patch((state) => {
    for (let [key, value] of Object.entries(data)) {
      if (typeof state.settings[key] === "object") {
        for (let [sub_key, sub_value] of Object.entries(value)) {
          state.settings[key][sub_key] = sub_value;
        }
      } else {
        state.settings[key] = value;
      }
    }
  });
};

const validateAndSaveSettings = function (store, data) {
  let redirect = validateFirstSearch(store, data);
  redirect = validateNewTopGroupIsParent(store, data, redirect);

  // Mutate settings
  if (data) {
    mutateSettings(store, data);
  }

  // clear choices and reset filter menu mode.
  if (data.filters || data.autoquery) {
    let filterName;
    if (data.filters) {
      filterName = Object.keys(data.filters)[0];
    }
    store.$patch((state) => {
      clearAllFormChoicesExcept(state, filterName);
      state.filterMode = "base";
    });
  }

  store.setTimestamp();
  return redirect;
};

const compareRouteParams = function (a, b) {
  return a.group === b.group && +a.pk === +b.pk && +a.page === +b.page;
};

const redirectRoute = function (route) {
  if (route.params) {
    router.push(route).catch((error) => {
      console.debug(error);
    });
  }
};

export const useBrowserStore = defineStore("browser", {
  state: () => ({
    choices: {
      // static choices
      bookmark: CHOICES.browser.bookmarkFilter,
      groupNames: CHOICES.browser.groupNames,
      settingsGroup: CHOICES.browser.settingsGroup,
      // determined by api
      ...DYNAMIC_FILTERS,
    },
    settings: {
      filters: {
        bookmark: undefined,
        ...DYNAMIC_FILTERS,
      },
      autoquery: "",
      topGroup: undefined,
      orderBy: undefined,
      orderReverse: undefined,
      show: { ...SETTINGS_SHOW_DEFAULTS },
      ts: Date.now(),
    },
    page: {
      adminFlags: {
        // determined by api
        enableFolderView: undefined,
      },
      browserTitle: {
        parentName: undefined,
        groupName: undefined,
        groupCount: undefined,
      },
      coversTimestamp: 0,
      librariesExist: undefined,
      modelGroup: undefined,
      numPages: 1,
      objList: [],
      queries: [],
      routes: {
        up: undefined,
        last: undefined,
      },
    },
    // LOCAL UI
    filterMode: "base",
    isSettingsDrawerOpen: false,
    zeroPad: 0,
    browserPageLoaded: false,
  }),
  getters: {
    topGroupChoices(state) {
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
    filterNames(state) {
      return Object.keys(state.settings.filters).slice(1);
    },
    orderByChoices(state) {
      const choices = [];
      for (const item of Object.values(CHOICES.browser.orderBy)) {
        if (item.value === "path") {
          if (state.page.adminFlags.enableFolderView) {
            choices.push(item);
          }
        } else {
          choices.push(item);
        }
      }
      return Object.values(choices);
    },
    isCodexViewable() {
      return useAuthStore().isCodexViewable;
    },
  },
  actions: {
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    setTimestamp() {
      this.settings.ts = Date.now();
    },
    clearFiltersAndChoices() {
      this.$patch((state) => {
        state.filterMode = "base";
        state.settings.filters.bookmark = "ALL";
        for (let filterName of this.filterNames) {
          state.settings.filters[filterName] = [];
        }
      });

      clearAllFormChoicesExcept(this);
      this.setTimestamp();
      return this.loadBrowserPage();
    },
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
    routeToPage(page) {
      const route = {
        name: router.currentRoute.name,
        params: { ...router.currentRoute.params, page },
      };
      router.push(route).catch((error) => {
        console.debug(error);
      });
    },
    handlePageError(error) {
      if (error.response.status == 303) {
        const data = error.response.data;
        if (compareRouteParams(data.route.params, router.currentRoute.params)) {
          this.setSettings(data.settings);
        } else {
          const redirect = validateAndSaveSettings(this, data.settings);
          if (redirect) {
            // ? i dunno if this is a good idea.
            data.route = redirect;
          }
          redirectRoute(data);
        }
      } else {
        return console.error(error);
      }
    },
    ///////////////////////////////////////////////////////////////////////////
    // LOAD
    async loadSettings() {
      if (!this.isCodexViewable) {
        return;
      }
      this.browserPageLoaded = false;
      clearAllFormChoicesExcept(this);
      await API.getSettings()
        .then((response) => {
          const data = response.data;
          const redirect = validateAndSaveSettings(this, data);
          this.browserPageLoaded = true;
          if (redirect) {
            return redirectRoute(redirect);
          }
          return this.loadBrowserPage();
        })
        .catch((error) => {
          this.browserPageLoaded = true;
          return this.handlePageError(error);
        });
    },
    async setSettings(data) {
      // Save settings to state and re-get the objects.
      const redirect = validateAndSaveSettings(this, data);
      await (redirect ? redirectRoute(redirect) : this.loadBrowserPage());
    },
    async loadBrowserPage() {
      // Get objects for the current route and settings.
      if (!this.isCodexViewable) {
        return;
      }
      if (!this.browserPageLoaded) {
        return this.loadSettings();
      }
      await API.loadBrowserPage(router.currentRoute.params, this.settings)
        .then((response) => {
          const data = response.data;
          this.$patch((state) => {
            const page = { ...response.data };
            page.routes = {
              up: data.upRoute,
              last: router.currentRoute.params,
            };
            page.zeroPad = getZeroPad(data.issueMax);
            delete page.upRoute;
            delete page.issueMax;

            state.page = Object.freeze(page);
          });
          return true;
        })
        .catch(this.handlePageError);
    },
    async setBookmarkFinished(params, finished) {
      if (!this.isCodexViewable) {
        return;
      }
      await API.setGroupBookmarks(params, { finished }).then(() => {
        this.setTimestamp();
        this.loadBrowserPage();
        return true;
      });
    },
    async loadFilterChoices(routeParams, mode) {
      await API.getBrowserChoices(routeParams, mode, this.settings)
        .then((response) => {
          this.choices[mode] = Object.freeze(response.data);
          return true;
        })
        .catch((error) => {
          console.error(error);
        });
    },
    async setFilterMode(routeParams, mode) {
      if (!this.isCodexViewable || !mode) {
        return;
      }
      if (mode !== "base" && this.choices[mode] === undefined) {
        this.loadFilterChoices(routeParams, mode);
      }
      this.filterMode = mode;
    },
  },
});
