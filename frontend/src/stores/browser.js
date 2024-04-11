import _ from "lodash";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import CHOICES from "@/choices";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

const GROUPS = "rpisvc";
Object.freeze(GROUPS);
const GROUPS_REVERSED = Array.from(GROUPS).reverse().join("");
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
  null,
  CHOICES.browser.bookmarkFilter[0].value,
]);
Object.freeze(DEFAULT_BOOKMARK_VALUES);
const ALWAYS_ENABLED_TOP_GROUPS = new Set(["a", "c"]);
Object.freeze(ALWAYS_ENABLED_TOP_GROUPS);

const getZeroPad = function (issueNumberMax) {
  return !issueNumberMax || issueNumberMax < 1
    ? 1
    : Math.floor(Math.log10(issueNumberMax)) + 1;
};
const redirectRoute = function (route) {
  if (route && route.params) {
    router.push(route).catch(console.warn);
  }
};
const createReadingDirection = function () {
  const rd = {};
  for (const obj of CHOICES.reader.readingDirection) {
    if (obj.value) {
      rd[obj.value] = obj.title;
    }
  }
  return rd;
};

export const useBrowserStore = defineStore("browser", {
  state: () => ({
    choices: {
      static: Object.freeze({
        bookmark: CHOICES.browser.bookmarkFilter,
        groupNames: CHOICES.browser.groupNames,
        settingsGroup: CHOICES.browser.settingsGroup,
        readingDirection: createReadingDirection(),
        identifierType: CHOICES.browser.identifierTypes,
      }),
      dynamic: undefined,
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
        folderView: undefined,
        importMetadata: undefined,
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
      groups: [],
      books: [],
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
        if (state.page.adminFlags.folderView && item.value === "path") {
          choices.push(item);
        }
        if (item.value == "search_score") {
          if (state.settings.q) {
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
      for (const [index, group] of Array.from(GROUPS_REVERSED).entries()) {
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
    parentModelGroup(state) {
      let group = "";
      if (!state.page || !state.page.routes || !state.page.routes.up) {
        return group;
      }
      const upGroup = state.page.routes.up.group;
      const index = GROUPS.indexOf(upGroup) + 1;
      const childGroups = GROUPS.slice(index);
      for (group of childGroups) {
        const show = state.settings.show[group];
        if (show) {
          break;
        }
      }
      return group;
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
    identifierTypeTitle(idType) {
      if (!idType) {
        return idType;
      }
      const lowerIdType = idType.toLowerCase();
      const longName = this.choices.static.identifierType[lowerIdType];
      return longName || idType;
    },
    ////////////////////////////////////////////////////////////////////////
    // VALIDATORS
    _isRootGroupEnabled(topGroup) {
      return ALWAYS_ENABLED_TOP_GROUPS.has(topGroup)
        ? true
        : topGroup == "f"
          ? this.page.adminFlags?.folderView
          : this.settings.show[topGroup];
    },
    _validateSearch(data) {
      if (!data.q) {
        // if cleared search check for bad order_by
        if (this.settings.orderBy === "search_score") {
          if (this.settings.topGroup === "f") {
            data.orderBy = "filename";
          } else {
            data.orderBy = "sort_name";
          }
        }
        return;
      } else if (this.q) {
        return;
      }
      // If first search redirect to lowest group and change order
      data.orderBy = "search_score";
      data.orderReverse = true;
      const group = router.currentRoute.value.params?.group;
      const noRedirectGroups = new Set(ALWAYS_ENABLED_TOP_GROUPS);
      noRedirectGroups.add(this.lowestShownGroup);
      if (noRedirectGroups.has(group)) {
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
      let redirect = this._validateSearch(data);
      redirect = this._validateNewTopGroupIsParent(data, redirect);

      // Add settings
      if (data) {
        this._addSettings(data);
      }

      this.filterMode = "base";
      return redirect;
    },
    async setSettings(data) {
      // Save settings to state and re-get the objects.
      const redirect = this._validateAndSaveSettings(data);
      useCommonStore().setTimestamp();
      this.browserPageLoaded = true;
      await (redirect ? redirectRoute(redirect) : this.loadBrowserPage());
    },
    async clearFilters() {
      this.settings.filters = {};
      await this.setSettings({});
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
          // Prevent settings reload in loadBrowserPage() erasing the set.
          this.browserPageLoaded = true;
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
        state.choices.dynamic = undefined;
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
      } else {
        this.browserPageLoaded = false;
      }
      const params = router.currentRoute.value.params;
      await API.loadBrowserPage(params, this.settings)
        .then((response) => {
          const data = response.data;
          const page = { ...response.data };
          delete page.upRoute;
          delete page.issueNumberMax;
          page.routes = {
            up: data.upRoute,
            last: params,
          };
          page.zeroPad = getZeroPad(data.issueNumberMax);
          this.$patch((state) => {
            state.page = Object.freeze(page);
            state.choices.dynamic = undefined;
            state.browserPageLoaded = true;
          });
          return true;
        })
        .catch(this.handlePageError);
    },
    async loadAvailableFilterChoices() {
      return await API.getAvailableFilterChoices(
        router.currentRoute.value.params,
        this.settings,
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
        this.settings,
      )
        .then((response) => {
          this.choices.dynamic[fieldName] = Object.freeze(response.data);
          return true;
        })
        .catch(console.error);
    },
  },
});
