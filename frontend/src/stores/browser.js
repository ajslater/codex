import _ from "lodash";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import CHOICES from "@/choices";
import router from "@/plugins/router";
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

const getZeroPad = function (issueMax) {
  return !issueMax || issueMax < 1 ? 1 : Math.floor(Math.log10(issueMax)) + 1;
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
    topGroupChoices() {
      const choices = [];
      for (const item of Object.values(CHOICES.browser.topGroup)) {
        if (this._isRootGroupEnabled(item.value)) {
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
    ////////////////////////////////////////////////////////////////////////
    // VALIDATORS
    _isRootGroupEnabled(topGroup) {
      return topGroup === "c" || topGroup === "f"
        ? this.page.adminFlags.enableFolderView
        : this.settings.show[topGroup];
    },
    _validateFirstSearch(data) {
      // If first search redirect to lowest group and change order
      if (this.q || !data.q) {
        // Not first search, validated.
        return;
      }
      data.orderBy = "search_score";
      data.orderReverse = true;
      let lowestGroup = "r";
      for (const key of GROUPS_REVERSED) {
        const val = this.settings.show[key];
        if (val) {
          lowestGroup = key;
          break;
        }
      }
      const params = router.currentRoute.value.params;
      if (params.group === lowestGroup) {
        return;
      }
      return { params: { ...params, group: lowestGroup } };
    },
    _validateNewTopGroupIsParent(data, redirect) {
      // If the top group changed and we're at the root group and the new top group is above the proper nav group
      const referenceRoute = redirect || router.currentRoute.value;
      const params = referenceRoute.params;
      if (
        params.group !== "r" ||
        !this.settings.topGroup ||
        GROUPS_REVERSED.indexOf(this.settings.topGroup) >=
          GROUPS_REVERSED.indexOf(data.topGroup)
      ) {
        // All is well, validated.
        return redirect;
      }
      const route = { params: { ...params } };

      let groupIndex = GROUPS_REVERSED.indexOf(this.settings.topGroup);
      const parentGroups = GROUPS_REVERSED.slice(groupIndex + 1);
      let jumpGroup;
      for (jumpGroup of parentGroups) {
        if (this.settings.show[jumpGroup]) {
          break;
        }
      }
      route.params.group = jumpGroup;
      return route;
    },
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    _mutateSettings(data) {
      this.$patch((state) => {
        for (let [key, value] of Object.entries(data)) {
          if (typeof state.settings[key] === "object") {
            state.settings[key] = { ...state.settings[key], ...value };
          } else {
            state.settings[key] = value;
          }
        }
      });
    },
    _validateAndSaveSettings(data) {
      let redirect = this._validateFirstSearch(data);
      redirect = this._validateNewTopGroupIsParent(data, redirect);

      // Mutate settings
      if (data) {
        this._mutateSettings(data);
      }

      this.filterMode = "base";
      this.setTimestamp();
      return redirect;
    },
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
      const redirect = this._validateAndSaveSettings(data);
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
      const route = _.cloneDeep(router.currentRoute.value);
      route.params.page = page;
      router.push(route).catch(console.debug);
    },
    handlePageError(error) {
      console.debug(error);
      if (error.response.status == 303) {
        const data = error.response.data;
        if (
          compareRouteParams(
            data.route.params,
            router.currentRoute.value.params
          )
        ) {
          this.setSettings(data.settings);
        } else {
          const redirect = this._validateAndSaveSettings(data.settings);
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
          const redirect = this._validateAndSaveSettings(data);
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
      const params = router.currentRoute.value.params;
      await API.loadBrowserPage(params, this.settings)
        .then((response) => {
          const data = response.data;
          this.$patch((state) => {
            const page = { ...response.data };
            page.routes = {
              up: data.upRoute,
              last: params,
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
    async loadAvailableFilterChoices() {
      return await API.getAvailableFilterChoices(
        router.currentRoute.value.params,
        this.settings
      )
        .then((response) => {
          this.choices.dynamic = response.data;
          return true;
        })
        .catch(console.error);
    },
    async loadFilterChoices(fieldName) {
      return await API.getFilterChoices(
        router.currentRoute.value.params,
        fieldName,
        this.settings
      )
        .then((response) => {
          this.choices.dynamic[fieldName] = Object.freeze(response.data);
          return true;
        })
        .catch(console.error);
    },
  },
});
