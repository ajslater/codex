import _ from "lodash";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import COMMON_API from "@/api/v3/common";
import CHOICES from "@/choices";
import { getTimestamp } from "@/datetime";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";

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
const SEARCH_HIDE_TIMEOUT = 5000;
const COVER_KEYS = ["customCovers", "dynamicCovers", "q"];
Object.freeze(COVER_KEYS);
const DYNAMIC_COVER_KEYS = ["filters", "orderBy", "orderReverse"];
Object.freeze(DYNAMIC_COVER_KEYS);
const CHOICES_KEYS = ["filters", "q"];
Object.freeze(CHOICES_KEYS);

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
      q: undefined,
      topGroup: undefined,
      orderBy: undefined,
      orderReverse: undefined,
      show: { ...SETTINGS_SHOW_DEFAULTS },
      /* eslint-disable-next-line no-secrets/no-secrets */
      // searchResultsLimit: CHOICES.browser.searchResultsLimit,
      twentyFourHourTime: false,
      dynamicCovers: false,
      customCovers: true,
    },
    page: {
      adminFlags: {
        // determined by api
        folderView: undefined,
        importMetadata: undefined,
      },
      breadcrumbs: CHOICES.browser.breadcrumbs,
      title: {
        groupName: undefined,
        groupCount: undefined,
      },
      librariesExist: undefined,
      modelGroup: undefined,
      numPages: 1,
      groups: [],
      books: [],
      mtime: 0,
    },
    // LOCAL UI
    filterMode: "base",
    zeroPad: 0,
    browserPageLoaded: false,
    isSearchOpen: false,
    searchHideTimeout: undefined,
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
        if (
          (item.value === "path" && !state.page.adminFlags.folderView) ||
          (item.value === "search_score" && !state.settings.q)
        ) {
          // denied order_by condition
          continue;
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
    isAuthorized() {
      return useAuthStore().isAuthorized;
    },
    isDynamicFiltersSelected(state) {
      for (const [name, array] of Object.entries(state.settings.filters)) {
        if (name !== "bookmark" && array && array.length > 0) {
          return true;
        }
      }
      return false;
    },
    isFiltersClearable(state) {
      const isDefaultBookmarkValueSelected = DEFAULT_BOOKMARK_VALUES.has(
        state.settings.filters.bookmark,
      );
      return !isDefaultBookmarkValueSelected || this.isDynamicFiltersSelected;
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
    isSearchMode(state) {
      return Boolean(state.settings.q);
    },
    /*
    isSearchLimitedMode(state) {
      return (
        Boolean(state.settings.q) && Boolean(state.settings.searchResultsLimit)
      );
    },
    */
    lastRoute(state) {
      const bc = state.page.breadcrumbs;
      const params = bc[bc.length - 1];
      const route = {};
      if (params) {
        route.name = "browser";
        route.params = params;
      } else {
        route.name = "home";
      }
      return route;
    },
    coverSettings(state) {
      const usedSettings = {};
      const group = router.currentRoute.value.params?.group;
      if (group != "c") {
        for (const [key, value] of Object.entries(state.settings)) {
          if (
            COVER_KEYS.includes(key) ||
            (state.settings.dynamicCovers && DYNAMIC_COVER_KEYS.includes(key))
          ) {
            usedSettings[key] = value;
          }
        }
      }
      return usedSettings;
    },
    choicesSettings(state) {
      const usedSettings = {};
      for (const [key, value] of Object.entries(state.settings)) {
        if (CHOICES_KEYS.includes(key)) {
          usedSettings[key] = value;
        }
      }
      return usedSettings;
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
    setIsSearchOpen(value) {
      this.isSearchOpen = value;
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
      } else if (this.settings.q || this.settings.q === undefined) {
        // undefined is browser open, do not redirect to first search.
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
      return { params: { group: this.lowestShownGroup, pks: "0", page: "1" } };
    },
    _validateTopGroup(data, redirect) {
      // If the top group changed supergroups or we're at the root group and the new
      // top group is above the proper nav group
      const oldTopGroup = this.settings.topGroup;
      const newTopGroup = data.topGroup;
      if (
        (!oldTopGroup && newTopGroup) ||
        !newTopGroup ||
        oldTopGroup === newTopGroup
      ) {
        // First url, initializing settings.
        // or
        // topGroup didn't change.
        // console.log("validate topGroup didn't change");
        return redirect;
      }
      const oldTopGroupIndex = GROUPS_REVERSED.indexOf(oldTopGroup);
      const newTopGroupIndex = GROUPS_REVERSED.indexOf(newTopGroup);
      const newTopGroupIsBrowse = newTopGroupIndex >= 0;
      const oldAndNewBothBrowseGroups =
        newTopGroupIsBrowse && oldTopGroupIndex >= 0;
      // console.log({ oldAndNewBothBrowseGroups, oldTopGroupIndex, newTopGroupIndex });

      // Construct and return new redirect
      let params;
      if (oldAndNewBothBrowseGroups) {
        if (oldTopGroupIndex < newTopGroupIndex) {
          // new top group is a parent (REVERSED)
          // Signal that we need new breadcrumbs. we do that by redirecting in place?
          params = router.currentRoute.value.params;
          // Make a numeric page so won't trigger the redirect remover and will always
          // redirect so we repopulate breadcrumbs
          params.page = +params.page;
          // console.log("new top group is parent", params);
        } else {
          // New top group is a child (REVERSED)
          // Redrect to the new root.
          params = { group: "r", pks: "0", page: "1" };
          // console.log("new top group is child", params);
        }
      } else {
        // redirect to the new TopGroup
        const group = newTopGroupIsBrowse ? "r" : newTopGroup;
        params = { group, pks: "0", page: "1" };
        // console.log("totally new top group", params);
      }
      return { params };
    },
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    _addSettings(data) {
      this.$patch((state) => {
        for (let [key, value] of Object.entries(data)) {
          let newValue;
          if (typeof state.settings[key] === "object") {
            newValue = { ...state.settings[key], ...value };
          } else {
            newValue = value;
          }
          if (!_.isEqual(state.settings[key], newValue)) {
            state.settings[key] = newValue;
          }
        }
        if (state.settings.q && !state.isSearchOpen) {
          state.isSearchOpen = true;
        }
      });
      this.startSearchHideTimeout();
    },
    _validateAndSaveSettings(data) {
      let redirect = this._validateSearch(data);
      redirect = this._validateTopGroup(data, redirect);
      if (_.isEqual(redirect?.params, router.currentRoute.value.params)) {
        // not triggered if page is numeric, which is intended.
        redirect = undefined;
      }

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
      this.browserPageLoaded = true;
      if (redirect) {
        await redirectRoute(redirect);
      } else {
        await this.loadBrowserPage();
      }
    },
    async clearFilters(clearSearch = false) {
      this.$patch((state) => {
        state.settings.filters = { bookmark: "" };
        state.filterMode = "base";
        if (clearSearch) {
          state.settings.q = "";
          state.settings.orderBy = "sort_name";
          state.settings.orderReverse = false;
        }
        state.browserPageLoaded = true;
      });
      await this.loadBrowserPage();
    },
    async setBookmarkFinished(params, finished) {
      if (!this.isAuthorized) {
        return;
      }
      await COMMON_API.setGroupBookmarks(params, { finished }).then(() => {
        this.loadBrowserPage(getTimestamp());
        return true;
      });
    },
    clearSearchHideTimeout() {
      clearTimeout(this.searchHideTimeout);
    },
    startSearchHideTimeout() {
      if (!this.isSearchOpen) {
        return;
      }
      const q = this.settings.q;
      if (q) {
        this.clearSearchHideTimeout();
      } else {
        this.searchHideTimeout = setTimeout(() => {
          const q = this.settings.q;
          if (!q) {
            this.setIsSearchOpen(false);
          }
        }, SEARCH_HIDE_TIMEOUT);
      }
    },
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
    routeToPage(page) {
      const route = _.cloneDeep(router.currentRoute.value);
      route.params.page = page;
      router.push(route).catch(console.warn);
    },
    handlePageError(error) {
      if (HTTP_REDIRECT_CODES.has(error?.response?.status)) {
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
      if (!this.isAuthorized) {
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
    async loadBrowserPage(mtime) {
      // Get objects for the current route and settings.
      if (!this.isAuthorized) {
        return;
      }
      const route = router.currentRoute.value;
      if (!mtime) {
        mtime = route.query.ts;
        if (!mtime) {
          mtime = this.page.mtime;
        }
      }
      if (!this.browserPageLoaded) {
        return this.loadSettings();
      } else {
        this.browserPageLoaded = false;
      }
      await API.loadBrowserPage(route.params, this.settings, mtime)
        .then((response) => {
          const page = Object.freeze({ ...response.data });
          this.$patch((state) => {
            state.page = page;
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
        this.choicesSettings,
        this.page.mtime,
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
        this.choicesSettings,
        this.page.mtime,
      )
        .then((response) => {
          this.choices.dynamic[fieldName] = Object.freeze(response.data);
          return true;
        })
        .catch(console.error);
    },
    async updateMtimes() {
      const route = router.currentRoute.value;
      const group =
        route.params.group != "r" ? route.params.group : this.page.modelGroup;
      const pks = route.params.pks;
      return await COMMON_API.getMtime([{ group, pks }], true)
        .then((response) => {
          const newMtime = response.data.maxMtime;
          // console.log(`new ${newMtime} !== old ${this.page.mtime}`);
          if (newMtime !== this.page.mtime) {
            this.choices.dynamic = undefined;
            this.loadBrowserPage(newMtime);
          }
        })
        .catch(console.error);
    },
  },
});
