import _ from "lodash";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import CHOICES from "@/choices";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

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
const HTTP_REDIRECT_CODES = new Set([301, 302, 303, 307, 308]);
Object.freeze(HTTP_REDIRECT_CODES);
const DEFAULT_BOOKMARK_VALUES = new Set([
  undefined,
  null, // eslint-disable-line unicorn/no-null
  CHOICES.browser.bookmarkFilter[0].value,
]);
Object.freeze(DEFAULT_BOOKMARK_VALUES);

const getZeroPad = function (issueMax) {
  return !issueMax || issueMax < 1 ? 1 : Math.floor(Math.log10(issueMax)) + 1;
};
const redirectRoute = function (route) {
  if (route && route.params) {
    router.push(route).catch(console.warn);
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
      twentyFourHourTime: undefined,
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
      routes: {
        up: undefined,
        last: undefined,
      },
    },
    // LOCAL UI
    filterMode: "base",
    zeroPad: 0,
    browserPageLoaded: false,
  }),
  getters: {
    topGroupChoices() {
      const choices = [];
      for (const item of CHOICES.browser.topGroup) {
        if (this._isRootGroupEnabled(item.value)) {
          /* XXX divider not implemented yet in Vuetify 3
          if (item.value === "f") {
            choices.push({ divider: true });
          }
          */
          choices.push(item);
        }
      }
      return choices;
    },
    topGroupChoicesMaxLen() {
      return this._maxLenChoices(CHOICES.browser.topGroup);
    },
    orderByChoices(state) {
      const choices = [];
      for (const item of CHOICES.browser.orderBy) {
        if (item.value === "path") {
          if (state.page.adminFlags.enableFolderView) {
            choices.push(item);
          }
        } else {
          choices.push(item);
        }
      }
      return choices;
    },
    orderByChoicesMaxLen() {
      return this._maxLenChoices(CHOICES.browser.orderBy);
    },
    filterByChoicesMaxLen() {
      return this._maxLenChoices(CHOICES.browser.bookmarkFilter);
    },
    isCodexViewable() {
      return useAuthStore().isCodexViewable;
    },
    isDefaultBookmarkValueSelected(state) {
      return DEFAULT_BOOKMARK_VALUES.has(state.settings.filters.bookmark);
    },
    lowestShownGroup(state) {
      let lowestGroup = "r";
      const topGroupIndex = GROUPS_REVERSED.indexOf(state.settings.topGroup);
      for (const [index, group] of [...GROUPS_REVERSED].entries()) {
        const show = state.settings.show[group];
        if (show) {
          if (index <= topGroupIndex) {
            lowestGroup = group;
          }
          break;
        }
      }
      return lowestGroup;
    },
  },
  actions: {
    ////////////////////////////////////////////////////////////////////////
    // UTILITY
    _maxLenChoices(choices) {
      let maxLen = 0;
      for (const item of choices) {
        if (item && item.title && item.title.length > maxLen) {
          maxLen = item.title.length;
        }
      }
      return maxLen;
    },
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
      const params = router.currentRoute.value.params;
      if (["f", this.lowestShownGroup].includes(params.group)) {
        return;
      }
      return { params: { group: this.lowestShownGroup, pk: 0, page: 1 } };
    },
    _validateNewTopGroupIsParent(data, redirect) {
      // If the top group changed and we're at the root group and the new top group is above the proper nav group
      const referenceRoute = redirect || router.currentRoute.value;
      const params = referenceRoute.params;
      const topGroupIndex = GROUPS_REVERSED.indexOf(this.settings.topGroup);
      if (
        params.group !== "r" ||
        !this.settings.topGroup ||
        topGroupIndex >= GROUPS_REVERSED.indexOf(data.topGroup)
      ) {
        // All is well, validated.
        return redirect;
      }

      // Construct and return new redirect
      const parentGroups = GROUPS_REVERSED.slice(topGroupIndex + 1);
      let group;
      for (group of parentGroups) {
        if (this.settings.show[group]) {
          break;
        }
      }
      return { params: { ...params, group } };
    },
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    _addSettings(data) {
      this.$patch((state) => {
        for (let [key, value] of Object.entries(data)) {
          state.settings[key] =
            typeof state.settings[key] === "object"
              ? { ...state.settings[key], ...value }
              : (state.settings[key] = value);
        }
      });
    },
    _validateAndSaveSettings(data) {
      let redirect = this._validateFirstSearch(data);
      redirect = this._validateNewTopGroupIsParent(data, redirect);

      // Add settings
      if (data) {
        this._addSettings(data);
      }

      this.filterMode = "base";
      return redirect;
    },
    async clearFilters() {
      this.settings.filters = {};
    },
    async setSettings(data) {
      // Save settings to state and re-get the objects.
      const redirect = this._validateAndSaveSettings(data);
      useCommonStore().setTimestamp();
      await (redirect ? redirectRoute(redirect) : this.loadBrowserPage());
    },
    async setBookmarkFinished(params, finished) {
      if (!this.isCodexViewable) {
        return;
      }
      await API.setGroupBookmarks(params, { finished }).then(() => {
        useCommonStore().setTimestamp();
        this.loadBrowserPage();
        return true;
      });
    },
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
    routeToPage(page) {
      const route = _.cloneDeep(router.currentRoute.value);
      route.params.page = page;
      router.push(route).catch(console.warn);
    },
    handlePageError(error) {
      if (HTTP_REDIRECT_CODES.has(error.response.status)) {
        console.debug(error);
        const data = error.response.data;
        if (data.settings) {
          this.setSettings(data.settings);
        }
        if (data.route) {
          redirectRoute(data.route);
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
            delete page.upRoute;
            delete page.issueMax;
            page.routes = {
              up: data.upRoute,
              last: params,
            };
            page.zeroPad = getZeroPad(data.issueMax);
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
