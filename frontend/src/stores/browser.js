import { dequal } from "dequal";
import { defineStore } from "pinia";
import { toRaw } from "vue";
import { dedupedFetch, isAbortError, useAbortable } from "@/api/v3/abortable";
import * as API from "@/api/v3/browser";
import * as COMMON_API from "@/api/v3/common";
import BROWSER_CHOICES from "@/choices/browser-choices.json";
import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
import { IDENTIFIER_SOURCES, TOP_GROUP } from "@/choices/browser-map.json";
import { READING_DIRECTION } from "@/choices/reader-map.json";
import { getTimestamp } from "@/datetime";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";

const GROUPS = Object.freeze("rpisvc");
export const GROUPS_REVERSED = Object.freeze([...GROUPS].reverse().join(""));
const HTTP_REDIRECT_CODES = Object.freeze(new Set([301, 302, 303, 307, 308]));
const DEFAULT_BOOKMARK_VALUES = Object.freeze(
  new Set([undefined, null, BROWSER_DEFAULTS.bookmarkFilter]),
);
const ALWAYS_ENABLED_TOP_GROUPS = Object.freeze(new Set(["a", "c"]));
const NO_REDIRECT_ON_SEARCH_GROUPS = Object.freeze(new Set(["a", "c", "f"]));
const NON_BROWSE_GROUPS = Object.freeze(new Set(["a", "f"]));
const SEARCH_HIDE_TIMEOUT = 5000;
const COVER_KEYS = Object.freeze(["customCovers", "dynamicCovers", "show"]);
const DYNAMIC_COVER_KEYS = Object.freeze([
  "filters",
  "orderBy",
  "orderReverse",
  "q",
]);
const FILTER_ONLY_KEYS = Object.freeze(["filters", "q"]);
const METADATA_LOAD_KEYS = Object.freeze(["filters", "q", "mtime"]);

function cloneRoute(route) {
  return {
    ...route,
    matched: route.matched.map(({ instances, ...rest }) => ({
      ...rest,
    })),
  };
}

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
        bookmark: BROWSER_CHOICES.BOOKMARK_FILTER,
        groupNames: TOP_GROUP,
        settingsGroup: BROWSER_CHOICES.SETTINGS_GROUP,
        readingDirection: READING_DIRECTION,
        identifierSources: IDENTIFIER_SOURCES,
      }),
      dynamic: undefined,
    },
    settings: {
      breadcrumbs: [],
      customCovers: BROWSER_DEFAULTS.customCovers,
      dynamicCovers: BROWSER_DEFAULTS.dynamicCovers,
      filters: BROWSER_DEFAULTS.filters,
      orderBy: BROWSER_DEFAULTS.orderBy,
      orderReverse: BROWSER_DEFAULTS.orderReverse,
      search: BROWSER_DEFAULTS.search,
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
    // Saved settings
    savedSettingsList: [],
    savedSettingsSnackbar: [],
  }),
  getters: {
    groupNames() {
      const groupNames = {};
      for (const [key, pluralName] of Object.entries(TOP_GROUP)) {
        groupNames[key] =
          pluralName === "Series" ? pluralName : pluralName.slice(0, -1);
      }
      return groupNames;
    },
    topGroupChoices() {
      const choices = [];
      for (const item of BROWSER_CHOICES.TOP_GROUP) {
        if (this._isRootGroupEnabled(item.value)) {
          choices.push(item);
        }
      }
      return choices;
    },
    topGroupChoicesMaxLen() {
      return this._maxLenChoices(BROWSER_CHOICES.TOP_GROUP);
    },
    orderByChoices(state) {
      const choices = [];
      for (const item of BROWSER_CHOICES.ORDER_BY) {
        if (
          (item.value === "path" && !state.page.adminFlags.folderView) ||
          (item.value === "child_count" && state.page.modelGroup === "c") ||
          (item.value === "search_score" &&
            (!state.settings.search || !state.page.fts))
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
      return this._maxLenChoices(BROWSER_CHOICES.ORDER_BY);
    },
    filterByChoicesMaxLen() {
      return this._maxLenChoices(BROWSER_CHOICES.BOOKMARK_FILTER);
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
      return Boolean(state.settings.search);
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
      if (!this.settings.search && !data.search) {
        // if cleared search check for bad order_by
        if (this.settings.orderBy === "search_score") {
          data.orderBy =
            this.settings.topGroup === "f" ? "filename" : "sort_name";
        }
        return;
      } else if (this.settings.search) {
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
        if (state.settings.search && !state.isSearchOpen) {
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
    async clearFilters(clearAll = false) {
      await API.resetSettings()
        .then((response) => {
          const data = response.data;
          this.$patch((state) => {
            state.settings.filters = data.filters;
            state.filterMode = "base";
            if (clearAll) {
              state.settings.search = data.search;
              state.settings.orderBy = data.orderBy;
              state.settings.orderReverse = data.orderReverse;
            }
            state.browserPageLoaded = true;
          });
        })
        .catch(console.error);
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
      const search = this.settings.search;
      if (search || this.isSearchHelpOpen) {
        this.clearSearchHideTimeout();
      } else {
        this.searchHideTimeout = setTimeout(() => {
          const search = this.settings.search;
          if (!search) {
            this.setIsSearchOpen(false);
          }
        }, SEARCH_HIDE_TIMEOUT);
      }
    },
    setSearchHelpOpen(value) {
      this.isSearchHelpOpen = value;
      this.startSearchHideTimeout();
    },
    /*
     * ROUTE
     */
    routeToPage(page) {
      const origRoute = router.currentRoute.value;
      const route = cloneRoute(origRoute);
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
      // Single-flight: a rapid group switch aborts the previous
      // fetch so its late-arriving response can't ``$patch`` stale
      // state over the current route's data.
      const signal = useAbortable("browser:loadBrowserPage");
      try {
        const response = await API.getBrowserPage(
          route.params,
          this.settings,
          mtime,
          { signal },
        );
        const { breadcrumbs, ...page } = response.data;
        this.$patch((state) => {
          state.settings.breadcrumbs = Object.freeze(breadcrumbs);
          state.page = Object.freeze(page);
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
      } catch (error) {
        if (isAbortError(error)) return;
        this.handlePageError(error);
      }
      if (updateSettings) {
        API.updateSettings(this.settings);
      }
    },
    async loadAvailableFilterChoices() {
      const signal = useAbortable("browser:loadAvailableFilterChoices");
      try {
        const response = await API.getAvailableFilterChoices(
          router.currentRoute.value.params,
          this.filterOnlySettings,
          this.page.mtime,
          { signal },
        );
        this.choices.dynamic = response.data;
        return true;
      } catch (error) {
        if (isAbortError(error)) return;
        console.error(error);
      }
    },
    async loadFilterChoices(fieldName) {
      // Per-field key so different filter menus opening in parallel
      // don't abort each other.
      const signal = useAbortable(`browser:loadFilterChoices:${fieldName}`);
      try {
        const response = await API.getFilterChoices(
          router.currentRoute.value.params,
          fieldName,
          this.filterOnlySettings,
          this.page.mtime,
          { signal },
        );
        this.choices.dynamic[fieldName] = Object.freeze(response.data.choices);
        return true;
      } catch (error) {
        if (isAbortError(error)) return;
        console.error(error);
      }
    },
    async loadMtimes() {
      const params = router?.currentRoute?.value?.params;
      const routeGroup = params?.group;
      const group =
        routeGroup && routeGroup != "r" ? routeGroup : this.page.modelGroup;
      const pks = params?.pks || "0";
      const arcs = [{ group, pks }];
      // Dedup so concurrent callers (websocket fan-out across the
      // browser + reader stores, rapid notifications) share one
      // request instead of stampeding.
      const dedupKey = `browser:loadMtimes:${group}:${pks}`;
      try {
        const response = await dedupedFetch(dedupKey, () =>
          COMMON_API.getMtime(arcs, this.filterOnlySettings),
        );
        const newMtime = response?.data?.maxMtime;
        if (newMtime !== this.page.mtime) {
          this.choices.dynamic = undefined;
          this.loadBrowserPage(newMtime);
        }
        return true;
      } catch (error) {
        console.error(error);
      }
    },
    routeWithSettings(settings, route) {
      if (!route) {
        return;
      }
      this._validateAndSaveSettings(settings);
      // ignore redirect
      router.push(route).catch(console.error);
    },
    /*
     * SAVED SETTINGS
     */
    async loadSavedSettingsList() {
      if (!this.isAuthorized) {
        return;
      }
      await API.getSavedSettingsList()
        .then((response) => {
          this.savedSettingsList = Object.freeze(
            response.data.savedSettings || [],
          );
          return true;
        })
        .catch(console.error);
    },
    async saveCurrentSettings(name) {
      if (!this.isAuthorized) {
        return;
      }
      await API.saveSettings(name)
        .then(() => {
          this.loadSavedSettingsList();
          return true;
        })
        .catch(console.error);
    },
    async loadSavedSettings(pk) {
      if (!this.isAuthorized) {
        return;
      }
      await API.loadSavedSettings(pk)
        .then((response) => {
          const { settings, filterWarnings } = response.data;
          if (settings) {
            this._validateAndSaveSettings(settings);
            this.browserPageLoaded = true;
            this.loadBrowserPage(undefined, true);
          }
          if (filterWarnings && filterWarnings.length > 0) {
            this.savedSettingsSnackbar = filterWarnings;
          }
          return true;
        })
        .catch(console.error);
    },
    async deleteSavedSettings(pk) {
      if (!this.isAuthorized) {
        return;
      }
      await API.deleteSavedSettings(pk)
        .then(() => {
          this.loadSavedSettingsList();
          return true;
        })
        .catch(console.error);
    },
    clearSavedSettingsSnackbar() {
      this.savedSettingsSnackbar = [];
    },
  },
});
