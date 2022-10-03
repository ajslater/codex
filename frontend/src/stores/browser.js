import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import CHOICES from "@/choices";
import router from "@/router";
import { useAuthStore } from "@/stores/auth";

export const NUMERIC_FILTERS = [
  "communityRating",
  "criticalRating",
  "decade",
  "year",
];
Object.freeze(NUMERIC_FILTERS);
export const CHARPK_FILTERS = ["ageRating", "country", "format", "language"];
Object.freeze(CHARPK_FILTERS);
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

const validateFirstSearch = function (state, data) {
  // If first search redirect to lowest group and change order
  if (state.q || !data.q) {
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
        state.settings[key] = { ...state.settings[key], ...value };
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

  store.filterMode = "base";
  store.setTimestamp();
  return redirect;
};

const compareRouteParams = function (a, b) {
  return a.group === b.group && +a.pk === +b.pk && +a.page === +b.page;
};

const redirectRoute = function (route) {
  if (route.params) {
    router.push(route).catch(console.debug);
  }
};

export const useBrowserStore = defineStore("browser", {
  state: () => ({
    choices: {
      static: Object.freeze({
        bookmark: CHOICES.browser.bookmarkFilter,
        groupNames: CHOICES.browser.groupNames,
        settingsGroup: CHOICES.browser.settingsGroup,
      }),
      dynamic: {},
    },
    settings: {
      filters: {},
      q: "",
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
    async clearFiltersAndChoices() {
      this.$patch((state) => {
        state.filterMode = "base";
        state.settings.filters = {};
        state.choices.dynamic = {};
        state.settings.ts = Date.now();
      });
      await this.loadBrowserPage();
    },
    async setSettings(data) {
      // Save settings to state and re-get the objects.
      const redirect = validateAndSaveSettings(this, data);
      await (redirect ? redirectRoute(redirect) : this.loadBrowserPage());
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
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
    routeToPage(page) {
      const route = {
        name: router.currentRoute.name,
        params: { ...router.currentRoute.params, page },
      };
      router.push(route).catch(console.debug);
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
      this.$patch((state) => {
        state.browserPageLoaded = false;
        state.choices.dynamic = {};
      });
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
            state.choices.dynamic = {};
          });
          return true;
        })
        .catch(this.handlePageError);
    },
    async loadAllFilterChoices() {
      return await API.getAllBrowserChoices(
        router.currentRoute.params,
        this.settings
      )
        .then((response) => {
          this.choices.dynamic = Object.freeze(response.data);
          return true;
        })
        .catch(console.error);
    },
  },
});
