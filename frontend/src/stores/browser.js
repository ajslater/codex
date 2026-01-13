import deepClone from "deep-clone";
import { dequal } from "dequal";
import { defineStore } from "pinia";

import API from "@/api/v3/browser";
import COMMON_API from "@/api/v3/common";
import BROWSER_CHOICES from "@/choices/browser-choices.json";
import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
import {
  identifierSources as IDENTIFIER_SOURCES,
  topGroup as GROUP_NAMES,
} from "@/choices/browser-map.json";
import { readingDirection as READING_DIRECTION } from "@/choices/reader-map.json";
import { getTimestamp } from "@/datetime";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { range } from "@/util";

const GROUPS = "rpisvc";
Object.freeze(GROUPS);
export const GROUPS_REVERSED = [...GROUPS].reverse().join("");
Object.freeze(GROUPS_REVERSED);
const HTTP_REDIRECT_CODES = new Set([301, 302, 303, 307, 308]);
Object.freeze(HTTP_REDIRECT_CODES);
const DEFAULT_BOOKMARK_VALUES = new Set([
  undefined,

  null,
  BROWSER_DEFAULTS.bookmarkFilter,
]);
Object.freeze(DEFAULT_BOOKMARK_VALUES);
const ALWAYS_ENABLED_TOP_GROUPS = new Set(["a", "c"]);
Object.freeze(ALWAYS_ENABLED_TOP_GROUPS);
const NO_REDIRECT_ON_SEARCH_GROUPS = new Set(["a", "c", "f"]);
Object.freeze(NO_REDIRECT_ON_SEARCH_GROUPS);
const NON_BROWSE_GROUPS = new Set(["a", "f"]);
Object.freeze(NON_BROWSE_GROUPS);
const SEARCH_HIDE_TIMEOUT = 5000;
const COVER_KEYS = ["customCovers", "dynamicCovers", "show"];
Object.freeze(COVER_KEYS);
const DYNAMIC_COVER_KEYS = ["filters", "orderBy", "orderReverse", "q"];
Object.freeze(DYNAMIC_COVER_KEYS);
const FILTER_ONLY_KEYS = ["filters", "q"];
Object.freeze(FILTER_ONLY_KEYS);
const PAGE_LOAD_KEYS = ["breadcrumbs"];
Object.freeze(PAGE_LOAD_KEYS);
const METADATA_LOAD_KEYS = ["filters", "q", "mtime"];
Object.freeze(METADATA_LOAD_KEYS);

const redirectRoute = (route) => {
  if (route && route.params) {
    router.push(route).catch(console.warn);
  }
};

const notEmptyOrBool = (value) => {
  return (value && Object.keys(value).length > 0) || typeof value === "boolean";
};

export const useBrowserStore = defineStore("browser", {
  state: () => ({
    choices: {
      static: Object.freeze({
        bookmark: BROWSER_CHOICES.bookmarkFilter,
        groupNames: GROUP_NAMES,
        settingsGroup: BROWSER_CHOICES.settingsGroup,
        readingDirection: READING_DIRECTION,
        identifierSources: IDENTIFIER_SOURCES,
      }),
      dynamic: undefined,
    },
    settings: {
      breadcrumbs: BROWSER_DEFAULTS.breadcrumbs,
      customCovers: BROWSER_DEFAULTS.customCovers,
      dynamicCovers: BROWSER_DEFAULTS.dynamicCovers,
      filters: {},
      orderBy: BROWSER_DEFAULTS.orderBy,
      orderReverse: BROWSER_DEFAULTS.orderReverse,
      q: BROWSER_DEFAULTS.q,
      show: BROWSER_DEFAULTS.show,
      topGroup: BROWSER_DEFAULTS.topGroup,
      twentyFourHourTime: BROWSER_DEFAULTS.twentyFourHourTime,
    },
    page: {
      adminFlags: {
        // determined by api
        folderView: undefined,
        importMetadata: undefined,
      },
      title: {
        groupName: undefined,
        groupCount: undefined,
      },
      librariesExist: undefined,
      modelGroup: undefined,
      numPages: 1,
      groups: [],
      books: [],
      fts: undefined,
      searchError: undefined,
      mtime: 0,
    },
    // LOCAL UI
    filterMode: "base",
    zeroPad: 0,
    browserPageLoaded: false,
    isSearchOpen: false,
    isSearchHelpOpen: false,
    searchHideTimeout: undefined,
  }),
  getters: {
    groupNames() {
      const groupNames = {};
      for (const [key, pluralName] of Object.entries(GROUP_NAMES)) {
        groupNames[key] =
          pluralName === "Series" ? pluralName : pluralName.slice(0, -1);
      }
      return groupNames;
    },
    topGroupChoices() {
      const choices = [];
      for (const item of BROWSER_CHOICES.topGroup) {
        if (this._isRootGroupEnabled(item.value)) {
          choices.push(item);
        }
      }
      return choices;
    },
    topGroupChoicesMaxLen() {
      return this._maxLenChoices(BROWSER_CHOICES.topGroup);
    },
    orderByChoices(state) {
      const choices = [];
      for (const item of BROWSER_CHOICES.orderBy) {
        if (
          (item.value === "path" && !state.page.adminFlags.folderView) ||
          (item.value === "child_count" && state.page.modelGroup === "c") ||
          (item.value === "search_score" &&
            (!state.settings.q || !state.page.fts))
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
      return this._maxLenChoices(BROWSER_CHOICES.orderBy);
    },
    filterByChoicesMaxLen() {
      return this._maxLenChoices(BROWSER_CHOICES.bookmarkFilter);
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
    isSearchMode(state) {
      return Boolean(state.settings.q);
    },
    lastRoute(state) {
      const params =
        state.settings?.breadcrumbs?.at(-1) || globalThis.CODEX.LAST_ROUTE;
      const route = {};
      if (params) {
        route.name = "browser";
        delete params.name;
        route.params = params;
      } else {
        route.name = "home";
      }
      return route;
    },
    coverSettings(state) {
      const params = router.currentRoute.value.params;
      const group = params.group;
      if (group == "c") {
        return {};
      }
      let keys = COVER_KEYS;
      const dc = state.settings.dynamicCovers;
      if (dc) {
        keys = [...keys, ...DYNAMIC_COVER_KEYS];
      }

      const settings = this._filterSettings(state, keys);
      const pks = params.pks;
      if (!dc && group !== "r" && pks) {
        settings["parentRoute"] = {
          group,
          pks,
        };
      }
      return settings;
    },
    filterOnlySettings(state) {
      return this._filterSettings(state, FILTER_ONLY_KEYS);
    },
    pageLoadSettings(state) {
      return this._filterSettings(state, PAGE_LOAD_KEYS);
    },
    metadataSettings(state) {
      return this._filterSettings(state, METADATA_LOAD_KEYS);
    },
    routeKey() {
      const params = router.currentRoute.value.params;
      return `${params.group}:${params.pk}:${params.page}`;
    },
  },
  actions: {
    /*
     * UTILITY
     */
    _filterSettings(state, keys) {
      return Object.fromEntries(
        Object.entries(state.settings).filter(([k, v]) => {
          if (!keys.includes(k)) {
            return null;
          }
          if (k === "filters") {
            const usedFilters = {};
            for (const [subkey, subvalue] of Object.entries(v)) {
              if (notEmptyOrBool(subvalue)) {
                usedFilters[subkey] = subvalue;
              }
            }
            v = usedFilters;
          }
          if (notEmptyOrBool(v)) {
            return [k, v];
          }
        }),
      );
    },
    _maxLenChoices(choices) {
      let maxLen = 0;
      for (const item of choices) {
        if (item && item.title && item.title.length > maxLen) {
          maxLen = item.title.length;
        }
      }
      return maxLen;
    },
    identifierSourceTitle(idSource) {
      if (!idSource) {
        return idSource;
      }
      const lowerIdSource = idSource.toLowerCase();
      const longName = this.choices.static.identifierSources[lowerIdSource];
      return longName || idSource;
    },
    fixUniverseTitles(universes) {
      const items = [];
      for (const oldItem of universes) {
        const item = { ...oldItem };
        if (item.designation) {
          item.name += ` (${item.designation})`;
        }
        items.push(item);
      }
      return items;
    },
    setIsSearchOpen(value) {
      this.isSearchOpen = value;
    },
    /*
     * VALIDATORS
     */
    _isRootGroupEnabled(topGroup) {
      if (ALWAYS_ENABLED_TOP_GROUPS.has(topGroup)) {
        return true;
      } else if (topGroup == "f") {
        return this.page.adminFlags?.folderView;
      } else {
        return this.settings.show[topGroup];
      }
    },
    _validateSearch(data) {
      if (!this.settings.q && !data.q) {
        // if cleared search check for bad order_by
        if (this.settings.orderBy === "search_score") {
          data.orderBy =
            this.settings.topGroup === "f" ? "filename" : "sort_name";
        }
        return;
      } else if (this.settings.q) {
        // Do not redirect to first search if already in search mode.
        return;
      }
      // If first search redirect to lowest group and change order
      data.orderBy = "search_score";
      data.orderReverse = true;
      const group = router.currentRoute.value.params?.group;
      if (
        NO_REDIRECT_ON_SEARCH_GROUPS.has(group) ||
        group === this.lowestShownGroup
      ) {
        return;
      }
      return { params: { group: this.lowestShownGroup, pks: "0", page: "1" } };
    },
    _validateTopGroup(data, redirect) {
      /*
       * If the top group changed supergroups or we're at the root group and the new
       * top group is above the proper nav group
       */
      const currentParams = router?.currentRoute?.value?.params;
      const currentGroup = currentParams?.group;
      const newTopGroup = data.topGroup;
      if (currentGroup === "r" && !NON_BROWSE_GROUPS.has(data.topGroup)) {
        return redirect;
        // r group can have any top groups?
      }

      const oldTopGroup = this.settings.topGroup;
      if (
        oldTopGroup === newTopGroup ||
        !newTopGroup ||
        (!oldTopGroup && newTopGroup) ||
        newTopGroup === currentGroup
      ) {
        /*
         * First url, initializing settings.
         * or
         * topGroup didn't change.
         * or
         * topGroup and group are the same, request is well formed.
         */
        return redirect;
      }
      const oldTopGroupIndex = GROUPS_REVERSED.indexOf(oldTopGroup);
      const newTopGroupIndex = GROUPS_REVERSED.indexOf(newTopGroup);
      const newTopGroupIsBrowse = newTopGroupIndex !== -1;
      const oldAndNewBothBrowseGroups =
        newTopGroupIsBrowse && oldTopGroupIndex !== -1;

      // Construct and return new redirect
      let params;
      if (oldAndNewBothBrowseGroups) {
        if (oldTopGroupIndex < newTopGroupIndex) {
          /*
           * new top group is a parent (REVERSED)
           * Signal that we need new breadcrumbs. we do that by redirecting in place?
           */
          params = currentParams;
          /*
           * Make a numeric page so won't trigger the redirect remover and will always
           * redirect so we repopulate breadcrumbs
           */
          params.page = +params.page;
        } else {
          /*
           * New top group is a child (REVERSED)
           * Redirect to the new root.
           */
          params = { group: "r", pks: "0", page: "1" };
        }
      } else {
        // redirect to the new TopGroup
        const group = newTopGroupIsBrowse ? "r" : newTopGroup;
        params = { group, pks: "0", page: "1" };
      }
      return { params };
    },
    getTopGroup(group) {
      // Similar to browser store logic.
      let topGroup;
      if (this.settings.topGroup === group || NON_BROWSE_GROUPS.has(group)) {
        topGroup = group;
      } else {
        const groupIndex = GROUPS_REVERSED.indexOf(group); // + 1;
        // Determine browse top group
        for (const testGroup of GROUPS_REVERSED.slice(groupIndex)) {
          if (testGroup !== "r" && this.settings.show[testGroup]) {
            topGroup = testGroup;
            break;
          }
        }
      }
      return topGroup;
    },
    /*
     * MUTATIONS
     */
    _addSettings(data) {
      this.$patch((state) => {
        for (let [key, value] of Object.entries(data)) {
          const newValue =
            typeof state.settings[key] === "object" &&
            !Array.isArray(state.settings[key])
              ? { ...state.settings[key], ...value }
              : value;
          if (!dequal(state.settings[key], newValue)) {
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
      if (dequal(redirect?.params, router.currentRoute.value.params)) {
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
        redirectRoute(redirect);
      } else {
        this.loadBrowserPage(undefined, true);
      }
    },
    async clearOneFilter(filterName) {
      this.$patch((state) => {
        state.filterMode = "base";
        state.settings.filters[filterName] = [];
        state.browserPageLoaded = true;
      });
      await this.loadBrowserPage(undefined, true);
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
      await this.loadBrowserPage(undefined, true);
    },
    async setBookmarkFinished(params, finished) {
      if (!this.isAuthorized) {
        return;
      }
      await API.updateGroupBookmarks(params, this.filterOnlySettings, {
        finished,
      }).then(() => {
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
      if (q || this.isSearchHelpOpen) {
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
    setSearchHelpOpen(value) {
      this.isSearchHelpOpen = value;
      this.startSearchHideTimeout();
    },
    setPageMtime(mtime) {
      globalThis.mtime = mtime;
    },
    async updateBreadcrumbs(oldBreadcrumbs) {
      const breadcrumbs = this.settings.breadcrumbs || [];
      const indexes = range(breadcrumbs.length).reverse();
      for (const index of indexes) {
        const oldCrumb = oldBreadcrumbs[index];
        const newCrumb = breadcrumbs[index];
        if (!dequal(oldCrumb, newCrumb)) {
          if (newCrumb.name === null) {
            // For volumes
            newCrumb.name = "";
          }
          API.updateSettings({ breadcrumbs });
          break;
        }
      }
    },
    /*
     * ROUTE
     */
    routeToPage(page) {
      const route = deepClone(router.currentRoute.value);
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
    /*
     * LOAD
     */
    async loadSettings() {
      if (!this.isAuthorized) {
        return;
      }
      this.$patch((state) => {
        state.browserPageLoaded = false;
        state.choices.dynamic = undefined;
      });
      const group = router?.currentRoute?.value.params?.group;
      await API.getSettings({ group })
        .then((response) => {
          const data = response.data;
          const redirect = this._validateAndSaveSettings(data);
          this.browserPageLoaded = true;
          if (redirect) {
            return redirectRoute(redirect);
          }
          return this.loadBrowserPage(undefined);
        })
        .catch((error) => {
          this.browserPageLoaded = true;
          return this.handlePageError(error);
        });
    },
    async loadBrowserPage(mtime, updateSettings = false) {
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
      if (this.browserPageLoaded) {
        this.browserPageLoaded = false;
      } else {
        return this.loadSettings();
      }
      const oldBreadcrumbs = this.settings.breadcrumbs;
      await API.getBrowserPage(route.params, this.settings, mtime)
        .then((response) => {
          const { breadcrumbs, ...page } = response.data;
          Object.freeze({ page });
          this.$patch((state) => {
            state.settings.breadcrumbs = breadcrumbs;
            state.page = page;
            if (
              (state.settings.orderBy === "search_score" && !page.fts) ||
              (state.settings.orderBy === "child_count" &&
                page.modelGroup === "c")
            ) {
              state.settings.orderBy = "sort_name";
            }
            state.choices.dynamic = undefined;
            state.browserPageLoaded = true;
          });
          return true;
        })
        .catch(this.handlePageError);
      if (updateSettings) {
        API.updateSettings(this.settings);
      } else {
        this.updateBreadcrumbs(oldBreadcrumbs);
      }
    },
    async loadAvailableFilterChoices() {
      return await API.getAvailableFilterChoices(
        router.currentRoute.value.params,
        this.filterOnlySettings,
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
        this.filterOnlySettings,
        this.page.mtime,
      )
        .then((response) => {
          this.choices.dynamic[fieldName] = Object.freeze(
            response.data.choices,
          );
          return true;
        })
        .catch(console.error);
    },
    async loadMtimes() {
      const params = router?.currentRoute?.value?.params;
      const routeGroup = params?.group;
      const group =
        routeGroup && routeGroup != "r" ? routeGroup : this.page.modelGroup;
      const pks = params?.pks || "0";
      const arcs = [{ group, pks }];
      return await COMMON_API.getMtime(arcs, this.filterOnlySettings)
        .then((response) => {
          const newMtime = response?.data?.maxMtime;
          if (newMtime !== this.page.mtime) {
            this.choices.dynamic = undefined;
            this.loadBrowserPage(newMtime);
          }
          return true;
        })
        .catch(console.error);
    },
    routeWithSettings(settings, route) {
      if (!route) {
        return;
      }
      this._validateAndSaveSettings(settings);
      // ignore redirect
      router.push(route).catch(console.error);
    },
  },
});
