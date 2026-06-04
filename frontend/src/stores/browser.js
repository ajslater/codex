import { dequal } from "dequal";
import { defineStore } from "pinia";
import { toRaw } from "vue";
import {
  abortKey,
  dedupedFetch,
  isAbortError,
  useAbortable,
} from "@/api/v4/abortable";
import * as API from "@/api/v4/browser";
import * as COMMON_API from "@/api/v4/common";
import BROWSER_CHOICES from "@/choices/browser-choices.json";
import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
import { IDENTIFIER_SOURCES, TOP_COLLECTION } from "@/choices/browser-map.json";
import BROWSER_TABLE_DEFAULT_COLUMNS from "@/choices/browser-table-default-columns.json";
import { READING_DIRECTION } from "@/choices/reader-map.json";
import { getTimestamp } from "@/datetime";
import router from "@/plugins/router";
import {
  collectionForRoute,
  normalizeParentIds,
  routeForCollection,
} from "@/route";
import { useAuthStore } from "@/stores/auth";

// Browse-collection hierarchy, root → deepest. The store speaks the collection
// vocabulary end to end now; ``COLLECTIONS_REVERSED`` (deepest → root) drives the
// ``.indexOf`` hierarchy ordering in lowestShownCollection / getTopCollection / topCollection
// validation.
const COLLECTIONS = Object.freeze([
  "root",
  "publishers",
  "imprints",
  "series",
  "volumes",
  "comics",
]);
export const COLLECTIONS_REVERSED = Object.freeze([...COLLECTIONS].reverse());
const HTTP_REDIRECT_CODES = Object.freeze(new Set([301, 302, 303, 307, 308]));
const DEFAULT_BOOKMARK_VALUES = Object.freeze(
  new Set([undefined, null, BROWSER_DEFAULTS.bookmarkFilter]),
);
const ALWAYS_ENABLED_TOP_COLLECTIONS = Object.freeze(
  new Set(["arcs", "comics"]),
);
const NO_REDIRECT_ON_SEARCH_COLLECTIONS = Object.freeze(
  new Set(["arcs", "comics", "folders"]),
);
const NON_BROWSE_COLLECTIONS = Object.freeze(new Set(["arcs", "folders"]));
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

/*
 * Default-columns gating. ``imprint_name`` and ``volume_name`` lead
 * the per-top-collection default column tuples (see
 * ``BROWSER_TABLE_DEFAULT_COLUMNS``), but a user who has the
 * matching ``show.imprints`` / ``show.volumes`` flags off — i.e., they
 * hide imprints / volumes from breadcrumb navigation — almost certainly
 * doesn't want those columns leading their default column set
 * either. The backend mirrors this in ``default_columns_filtered``;
 * the two stay in sync via this constant.
 */
const _SHOW_GATED_COLUMNS = Object.freeze({
  imprint_name: "imprints",
  volume_name: "volumes",
});

export function filterShowGatedDefaults(cols, show) {
  if (!cols || cols.length === 0) return cols ?? [];
  const showMap = show && typeof show === "object" ? show : {};
  const blocked = new Set();
  for (const [col, flag] of Object.entries(_SHOW_GATED_COLUMNS)) {
    if (!showMap[flag]) blocked.add(col);
  }
  if (blocked.size === 0) return cols;
  return cols.filter((c) => !blocked.has(c));
}

/*
 * Per-top-collection default order applied when the user hits the
 * "Cancel" button on the loading spinner. Cover view, Folder,
 * StoryArc, Publisher and Comic top-collections all want the plain
 * ``sort_name`` single sort — Comic's order pipeline already
 * expands ``sort_name`` into the full
 * ``publisher_sort_name → ... → sort_name`` ladder via
 * ``_add_comic_order_by``, so a single key is enough.
 *
 * Imprint, Series and Volume in *table* mode want a multi-column
 * sort that respects the collection hierarchy: rows of an Imprint
 * list are sorted publisher-then-name; rows of a Series list are
 * publisher-then-imprint-then-name; rows of a Volume list are
 * publisher-then-imprint-then-series-then-name (Volume.sort_name
 * itself expands to ``name, number_to`` in
 * :func:`add_order_by`).
 */
const _DEFAULT_TABLE_ORDER = Object.freeze({
  imprints: Object.freeze({
    orderBy: "publisher_name",
    orderExtraKeys: [Object.freeze({ key: "sort_name", reverse: false })],
  }),
  series: Object.freeze({
    orderBy: "publisher_name",
    orderExtraKeys: [
      Object.freeze({ key: "imprint_name", reverse: false }),
      Object.freeze({ key: "sort_name", reverse: false }),
    ],
  }),
  volumes: Object.freeze({
    orderBy: "publisher_name",
    orderExtraKeys: [
      Object.freeze({ key: "imprint_name", reverse: false }),
      Object.freeze({ key: "series_name", reverse: false }),
      Object.freeze({ key: "sort_name", reverse: false }),
    ],
  }),
});

const _DEFAULT_SINGLE_ORDER = Object.freeze({
  orderBy: "sort_name",
  orderExtraKeys: [],
});

function _defaultOrderFor(topCollection, viewMode) {
  if (
    viewMode === "table" &&
    Object.hasOwn(_DEFAULT_TABLE_ORDER, topCollection)
  ) {
    return _DEFAULT_TABLE_ORDER[topCollection];
  }
  return _DEFAULT_SINGLE_ORDER;
}

/*
 * Read the live browser route as the internal {collection, pks, page} shape the
 * store logic expects. collection is the collection value ("publishers",
 * "series", …) with the synthetic "root" for the bare publishers list; pks is
 * the raw "5,7" parent-ids segment (or "" at root — no dummy 0 sentinel); page
 * is the ?page= query as a string (default "1") so the redirect/dequal matches.
 */
const liveBrowseParams = () => {
  const route = router.currentRoute.value;
  const parentIds = route.params.parentIds;
  const { collection } = collectionForRoute({
    collection: route.params.collection,
    parentIds,
  });
  const pks = parentIds || "";
  return { collection, pks, page: String(route.query.page || 1) };
};

/*
 * Convert an internal {name, params:{collection, pks, page}} browser route into
 * a pushable v4 collection route. Idempotent: an already-collection route passes
 * through. A numeric page is kept in the query even when 1 (the validate logic
 * uses a numeric page to force a breadcrumb-repopulating redirect); a string
 * "1" is dropped for a clean root URL.
 */
const toBrowseRoute = (route) => {
  const params = route?.params || {};
  // Accept either the v4 {collection, parentIds} dialect (backend route
  // objects: breadcrumbs, last_route, redirect.route) or the internal
  // {collection, pks} engine shape (client-built redirects, liveBrowseParams).
  // Both carry `collection`; disambiguate on which parent-ids key is present
  // (engine shapes always carry `pks`, even ""; v4 routes carry `parentIds`).
  let collection;
  let parentIds;
  if (params.pks === undefined) {
    collection = params.collection;
    parentIds = normalizeParentIds(params.parentIds);
  } else {
    ({ collection, parentIds } = routeForCollection({
      collection: params.collection,
      pks: params.pks,
    }));
  }
  const out = { name: route?.name || "browser", params: { collection } };
  if (parentIds.length) {
    out.params.parentIds = parentIds.join(",");
  }
  const query = { ...(route?.query || {}) };
  const page = params.page;
  if (
    page !== undefined &&
    (typeof page === "number" || String(page) !== "1")
  ) {
    query.page = Number(page);
  }
  if (Object.keys(query).length) {
    out.query = query;
  }
  if (route?.hash) {
    out.hash = route.hash;
  }
  return out;
};

const redirectRoute = (route) => {
  if (route && route.params) {
    router.push(toBrowseRoute(route)).catch(console.warn);
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
        collectionNames: TOP_COLLECTION,
        settingsCollection: BROWSER_CHOICES.SETTINGS_COLLECTION,
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
      orderExtraKeys: BROWSER_DEFAULTS.orderExtraKeys ?? [],
      search: BROWSER_DEFAULTS.search,
      show: BROWSER_DEFAULTS.show,
      topCollection: BROWSER_DEFAULTS.topCollection,
      twentyFourHourTime: BROWSER_DEFAULTS.twentyFourHourTime,
      viewMode: BROWSER_DEFAULTS.viewMode,
      tableColumns: BROWSER_DEFAULTS.tableColumns,
      tableCoverSize: BROWSER_DEFAULTS.tableCoverSize,
    },
    page: {
      adminFlags: {
        // determined by api
        folderView: undefined,
        importMetadata: undefined,
      },
      title: {
        collectionName: undefined,
        collectionCount: undefined,
      },
      librariesExist: undefined,
      modelCollection: undefined,
      numPages: 1,
      collections: [],
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
    collectionNames() {
      const collectionNames = {};
      for (const [key, pluralName] of Object.entries(TOP_COLLECTION)) {
        collectionNames[key] =
          pluralName === "Series" ? pluralName : pluralName.slice(0, -1);
      }
      return collectionNames;
    },
    topCollectionChoices() {
      const choices = [];
      for (const item of BROWSER_CHOICES.TOP_COLLECTION) {
        if (this._isRootCollectionEnabled(item.value)) {
          choices.push(item);
        }
      }
      return choices;
    },
    topCollectionChoicesMaxLen() {
      return this._maxLenChoices(BROWSER_CHOICES.TOP_COLLECTION);
    },
    orderByChoices(state) {
      /*
       * Cover view's dropdown filters down to a curated subset
       * (BROWSER_CHOICES.COVER_ORDER_BY_KEYS). The table view exposes
       * every sortable column via its own header clicks, so it doesn't
       * need this dropdown — but the dropdown can still come into
       * view momentarily during a viewMode transition or on mobile
       * fallback. The set is keyed for fast lookup.
       */
      const coverKeys = new Set(BROWSER_CHOICES.COVER_ORDER_BY_KEYS);
      const choices = [];
      for (const item of BROWSER_CHOICES.ORDER_BY) {
        if (
          !coverKeys.has(item.value) ||
          (item.value === "path" && !state.page.adminFlags.folderView) ||
          (item.value === "child_count" &&
            state.page.modelCollection === "comics") ||
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
      /*
       * "Dynamic" = anything beyond the default bookmark choice. The
       * favorite filter is a boolean (not a list-of-pks), but counts as
       * a non-default extra filter for the multi-filter chip indicator —
       * otherwise toggling Favorites-only would silently drop the icon
       * that signals "extra filters are active."
       */
      if (state.settings.filters.favorite) return true;
      for (const [name, array] of Object.entries(state.settings.filters)) {
        if (
          name !== "bookmark" &&
          name !== "favorite" &&
          array &&
          array.length > 0
        ) {
          return true;
        }
      }
      return false;
    },
    isFiltersClearable(state) {
      const isDefaultBookmarkValueSelected = DEFAULT_BOOKMARK_VALUES.has(
        state.settings.filters.bookmark,
      );
      const isFavoriteFilterOn = Boolean(state.settings.filters.favorite);
      return (
        !isDefaultBookmarkValueSelected ||
        isFavoriteFilterOn ||
        this.isDynamicFiltersSelected
      );
    },
    lowestShownCollection(state) {
      let lowestCollection = "root";
      const topCollectionIndex = COLLECTIONS_REVERSED.indexOf(
        state.settings.topCollection,
      );
      for (const [index, collection] of [...COLLECTIONS_REVERSED].entries()) {
        const show = state.settings.show[collection];
        if (show) {
          if (index <= topCollectionIndex) {
            lowestCollection = collection;
          }
          break;
        }
      }
      return lowestCollection;
    },
    isSearchMode(state) {
      return Boolean(state.settings.search);
    },
    lastRoute(state) {
      const params =
        state.settings?.breadcrumbs?.at(-1) || globalThis.CODEX.LAST_ROUTE;
      return params
        ? toBrowseRoute({ name: "browser", params })
        : { name: "home" };
    },
    coverSettings(state) {
      const { collection, pks } = liveBrowseParams();
      if (collection == "comics") {
        return {};
      }
      let keys = COVER_KEYS;
      const dc = state.settings.dynamicCovers;
      if (dc) {
        keys = [...keys, ...DYNAMIC_COVER_KEYS];
      }

      const settings = this._filterSettings(state, keys);
      if (!dc && collection !== "root" && pks) {
        settings["parentRoute"] = {
          collection,
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
      const { collection, pks, page } = liveBrowseParams();
      return `${collection}:${pks}:${page}`;
    },
  },
  actions: {
    /*
     * UTILITY
     */
    bustCoverCache({ ids, coverCustomPk }) {
      if (!ids?.length) return;
      const target = new Set(ids);
      const ts = Date.now();
      const updateRow = (row) => {
        if (!row?.ids?.some((pk) => target.has(pk))) return;
        row.coverCustomPk = coverCustomPk;
        row.mtime = ts;
      };
      for (const row of this.page.collections) updateRow(row);
      for (const row of this.page.books) updateRow(row);
    },
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
    _isRootCollectionEnabled(topCollection) {
      if (ALWAYS_ENABLED_TOP_COLLECTIONS.has(topCollection)) {
        return true;
      } else if (topCollection == "folders") {
        return this.page.adminFlags?.folderView;
      } else {
        return this.settings.show[topCollection];
      }
    },
    _validateSearch(data) {
      if (!this.settings.search && !data.search) {
        // if cleared search check for bad order_by
        if (this.settings.orderBy === "search_score") {
          data.orderBy =
            this.settings.topCollection === "folders"
              ? "filename"
              : "sort_name";
        }
        return;
      } else if (this.settings.search) {
        // Do not redirect to first search if already in search mode.
        return;
      }
      // If first search redirect to lowest collection and change order
      data.orderBy = "search_score";
      data.orderReverse = true;
      const collection = liveBrowseParams().collection;
      if (
        NO_REDIRECT_ON_SEARCH_COLLECTIONS.has(collection) ||
        collection === this.lowestShownCollection
      ) {
        return;
      }
      return {
        params: { collection: this.lowestShownCollection, pks: "", page: "1" },
      };
    },
    _validateTopCollection(data, redirect) {
      /*
       * If the top collection changed super-collections or we're at the root
       * collection and the new top collection is above the proper nav collection
       */
      const currentParams = liveBrowseParams();
      const currentCollection = currentParams?.collection;
      const newTopCollection = data.topCollection;
      if (
        currentCollection === "root" &&
        !NON_BROWSE_COLLECTIONS.has(data.topCollection)
      ) {
        return redirect;
        // root collection can have any top collections?
      }

      const oldTopCollection = this.settings.topCollection;
      if (
        oldTopCollection === newTopCollection ||
        !newTopCollection ||
        (!oldTopCollection && newTopCollection) ||
        newTopCollection === currentCollection
      ) {
        /*
         * First url, initializing settings.
         * or
         * topCollection didn't change.
         * or
         * topCollection and collection are the same, request is well formed.
         */
        return redirect;
      }
      const oldTopCollectionIndex =
        COLLECTIONS_REVERSED.indexOf(oldTopCollection);
      const newTopCollectionIndex =
        COLLECTIONS_REVERSED.indexOf(newTopCollection);
      const newTopCollectionIsBrowse = newTopCollectionIndex !== -1;
      const oldAndNewBothBrowseCollections =
        newTopCollectionIsBrowse && oldTopCollectionIndex !== -1;

      // Construct and return new redirect
      let params;
      if (oldAndNewBothBrowseCollections) {
        if (oldTopCollectionIndex < newTopCollectionIndex) {
          /*
           * new top collection is a parent (REVERSED)
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
           * New top collection is a child (REVERSED)
           * Redirect to the new root.
           */
          params = { collection: "root", pks: "", page: "1" };
        }
      } else {
        // redirect to the new TopCollection
        const collection = newTopCollectionIsBrowse ? "root" : newTopCollection;
        params = { collection, pks: "", page: "1" };
      }
      return { params };
    },
    getTopCollection(collection) {
      // Similar to browser store logic.
      let topCollection;
      if (
        this.settings.topCollection === collection ||
        NON_BROWSE_COLLECTIONS.has(collection)
      ) {
        topCollection = collection;
      } else {
        const collectionIndex = COLLECTIONS_REVERSED.indexOf(collection); // + 1;
        // Determine browse top collection
        for (const testCollection of COLLECTIONS_REVERSED.slice(
          collectionIndex,
        )) {
          if (testCollection !== "root" && this.settings.show[testCollection]) {
            topCollection = testCollection;
            break;
          }
        }
      }
      return topCollection;
    },
    /*
     * TABLE VIEW
     */
    _resolveTableColumns() {
      /*
       * Pick the column set for the current table-view request.
       * Persisted overrides (``settings.tableColumns[topCollection]``) win
       * over the registry defaults; both fall back to an empty tuple
       * for unknown top-collections (the backend then uses its own
       * defaults). Defaults are filtered by the user's ``show.i``
       * and ``show.v`` flags so a user who hides imprints / volumes
       * from breadcrumb navigation doesn't get those columns leading
       * their table view either.
       */
      const topCollection = this.settings.topCollection ?? "publishers";
      const stored = this.settings.tableColumns?.[topCollection];
      if (stored && stored.length > 0) {
        return stored;
      }
      return filterShowGatedDefaults(
        BROWSER_TABLE_DEFAULT_COLUMNS[topCollection] ?? [],
        this.settings.show,
      );
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
      redirect = this._validateTopCollection(data, redirect);
      if (dequal(redirect?.params, liveBrowseParams())) {
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
      await API.updateCollectionBookmarks(params, this.filterOnlySettings, {
        finished,
      }).then(() => {
        this.loadBrowserPage(getTimestamp());
        return true;
      });
    },
    async forceUpdateCollection(params) {
      if (!this.isAuthorized) {
        return;
      }
      await API.forceUpdateCollection(params, this.filterOnlySettings);
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
      const params = { ...liveBrowseParams(), page };
      router
        .push(toBrowseRoute({ name: "browser", params }))
        .catch(console.warn);
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
      const collection = liveBrowseParams().collection;
      await API.getSettings({ collection })
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
    async cancelBrowserPage() {
      /*
       * User-initiated cancel for a long-running browser request.
       * Surfaces in the UI as a "Cancel" button next to the
       * indeterminate spinner after a 10s grace period.
       *
       * Stays on the current route. Keeps filters, search, view-
       * mode, top-collection, columns, and every other display
       * preference. Only resets the order to the per-top-collection
       * default (see ``_defaultOrderFor``) so the next fetch lands
       * on a configuration the backend can serve quickly.
       *
       * Aborting fires the catch in ``loadBrowserPage`` which
       * swallows the AbortError; the follow-up ``setSettings``
       * call PATCHes the new order, re-loads, and persists. If no
       * request is actually pending we leave everything alone —
       * the spinner is showing for some other reason (initial
       * libraries fetch, settings load) and the cancel button
       * shouldn't have been clickable.
       */
      const aborted = abortKey("browser:loadBrowserPage");
      if (!aborted) return;
      const order = _defaultOrderFor(
        this.settings.topCollection,
        this.settings.viewMode,
      );
      await this.setSettings({
        orderBy: order.orderBy,
        orderReverse: false,
        orderExtraKeys: order.orderExtraKeys,
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
      /*
       * Single-flight: a rapid collection switch aborts the previous
       * fetch so its late-arriving response can't ``$patch`` stale
       * state over the current route's data.
       */
      const signal = useAbortable("browser:loadBrowserPage");
      /*
       * Table mode requests need ``columns=`` so the backend knows
       * which fields to project / annotate. The list comes from the
       * user's persisted table_columns map (per top-collection) and falls
       * back to the registry defaults; cover mode never sets it.
       */
      const requestSettings =
        this.settings.viewMode === "table"
          ? { ...this.settings, columns: this._resolveTableColumns().join(",") }
          : this.settings;
      try {
        const response = await API.getBrowserPage(
          liveBrowseParams(),
          requestSettings,
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
              page.modelCollection === "comics")
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
          liveBrowseParams(),
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
      /*
       * Per-field key so different filter menus opening in parallel
       * don't abort each other.
       */
      const signal = useAbortable(`browser:loadFilterChoices:${fieldName}`);
      try {
        const response = await API.getFilterChoices(
          { ...liveBrowseParams(), fieldName },
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
    /*
     * Refresh gate for ``library.changed`` (and groups/users) events.
     * The notification only says *something* changed, so probe the
     * scoped ``/api/v4/mtime`` for the currently-viewed collection and
     * reload only when its max mtime differs from the page we last
     * fetched — skipping a full reload for views the change didn't touch
     * instead of reloading on every broadcast.
     */
    async loadMtimes() {
      const { collection: routeCollection, pks } = liveBrowseParams();
      const collection =
        routeCollection && routeCollection != "root"
          ? routeCollection
          : this.page.modelCollection;
      // The mtime endpoint's pks field rejects blanks; the root list sends
      // the legacy "0" sentinel, which the route serializer strips back to
      // no-parent-ids (deferred-removal wire compat).
      const arcPks = pks || "0";
      const arcs = [{ collection, pks: arcPks }];
      /*
       * Dedup so concurrent callers (websocket fan-out across the
       * browser + reader stores, rapid notifications) share one
       * request instead of stampeding.
       */
      const dedupKey = `browser:loadMtimes:${collection}:${arcPks}`;
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
      router.push(toBrowseRoute(route)).catch(console.error);
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
