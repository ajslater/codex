import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { defineStore } from "pinia";
import { capitalCase } from "text-case";

import { dedupedFetch, isAbortError, useAbortable } from "@/api/v3/abortable";
import BROWSER_API from "@/api/v3/browser";
import COMMON_API from "@/api/v3/common";
import READER_API, { getComicPageSource } from "@/api/v3/reader";
import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
import READER_CHOICES from "@/choices/reader-choices.json";
import READER_DEFAULTS from "@/choices/reader-defaults.json";
import { getFullComicName } from "@/comic-name";
import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";

const SETTINGS_NULL_VALUES = Object.freeze(new Set(["", null, undefined]));

const DIRECTION_REVERSE_MAP = Object.freeze({
  prev: "next",
  next: "prev",
});
const PREFETCH_LINK = Object.freeze({ rel: "prefetch", as: "image" });
export const VERTICAL_READING_DIRECTIONS = Object.freeze(
  new Set(["ttb", "btt"]),
);
export const REVERSE_READING_DIRECTIONS = Object.freeze(
  new Set(["rtl", "btt"]),
);
export const SCALE_DEFAULT = 1;
const FIT_TO_CLASSES = Object.freeze({
  S: "Screen",
  W: "Width",
  H: "Height",
  O: "Original",
});
const BOOKS_NULL = Object.freeze({
  current: undefined,
  prev: false,
  next: false,
});
const ROUTES_NULL = Object.freeze({
  prev: false,
  next: false,
  books: {
    prev: false,
    next: false,
  },
  close: undefined,
});
const DEFAULT_ARC = Object.freeze({
  group: "s",
  ids: [],
});

const ensureNoTwoPageVertical = (settings) => {
  // No two pages with vertical
  if (
    VERTICAL_READING_DIRECTIONS.has(settings.readingDirection) &&
    settings.twoPages
  ) {
    settings.twoPages = false;
  }
};

export const useReaderStore = defineStore("reader", {
  state: () => ({
    // static
    choices: {
      fitTo: READER_CHOICES.FIT_TO,
      readingDirection: READER_CHOICES.READING_DIRECTION,
      nullValues: SETTINGS_NULL_VALUES,
    },

    // server
    globalSettings: {
      fitTo: READER_DEFAULTS.fitTo,
      twoPages: READER_DEFAULTS.twoPages,
      readingDirection: READER_DEFAULTS.readingDirection,
      readRtlInReverse: READER_DEFAULTS.readRtlInReverse,
      finishOnLastPage: READER_DEFAULTS.finishOnLastPage,
      pageTransition: READER_DEFAULTS.page_transition,
      cacheBook: READER_DEFAULTS.cache_book,
    },
    intermediateSettings: {},
    intermediateInfo: null,
    books: structuredClone(BOOKS_NULL),
    arcs: {},
    arc: { group: "s", ids: [] },
    mtime: 0,

    // local reader
    empty: false,
    page: undefined,
    routes: structuredClone(ROUTES_NULL),
    bookChange: undefined,
    reactWithScroll: false,
    clientSettings: {
      scale: SCALE_DEFAULT,
    },
    showToolbars: false,
    settingsLoaded: false,
    bookSettings: {},
  }),
  getters: {
    activeSettings(state) {
      // the empty settings guarantee here is for vitest.
      return this.getBookSettings(state.books.current) || {};
    },
    activeTitle(state) {
      const book = state.books.current;
      let title;
      if (book) {
        if (state.arc?.group != "f") {
          title = getFullComicName(book);
        }
        if (!title) {
          title = book.filename || "";
        }
      } else {
        title = "";
      }
      return title;
    },
    isVertical(state) {
      return state.activeSettings.isVertical;
    },
    isReadInReverse(state) {
      return state.activeSettings.isReadInReverse;
    },
    routeParams(state) {
      return { pk: +state.books.current.pk, page: +state.page };
    },
    isPDF(state) {
      return state.books?.current?.fileType == "PDF";
    },
    cacheBook() {
      return (
        this.activeSettings.cacheBook &&
        !(this.isPDF && this.activeSettings.isVertical)
      );
    },
    isPagesNotRoutes(state) {
      return state.activeSettings.isVertical || this.cacheBook;
    },
    isBTT(state) {
      return state.activeSettings.readingDirection === "btt";
    },
    isFirstPage(state) {
      return state.page === 0;
    },
    isLastPage(state) {
      const maxPage = state.books.current ? state.books.current.maxPage : 0;
      const adj = state.activeSettings.twoPages ? 1 : 0;
      const limit = maxPage - adj;
      return this.page >= limit;
    },
    closeBookRoute(state) {
      const route = { name: "browser" };
      if (state.routes.close) {
        route.params = state.routes.close;
      } else {
        const breadcrumbs = useBrowserStore()?.settings?.breadcrumbs;
        route.params = breadcrumbs?.findLast((b) => b.group !== "c");
      }
      if (route.params) {
        const cardPk = state.books?.current?.pk;
        if (cardPk) {
          route.hash = `#card-${cardPk}`;
        }
      } else {
        route.params =
          globalThis.CODEX.LAST_ROUTE || BROWSER_DEFAULTS.breadcrumbs[0];
      }
      return route;
    },
  },
  actions: {
    /*
     * GETTER Algorithms
     */
    setReadRTLInReverse(bookSettings) {
      // Special setting for RTL books
      return this.globalSettings.readRtlInReverse &&
        bookSettings.readingDirection === "rtl"
        ? { ...bookSettings, readingDirection: "ltr" }
        : bookSettings;
    },
    getBookSettings(book) {
      if (!book) {
        return {};
      }
      if (!(book.pk in this.bookSettings)) {
        /*
         * Mask the book settings over intermediate over global
         * settings into a fresh accumulator. The previous code
         * cloned ``SETTINGS_NULL_VALUES`` here, but that
         * constant is a ``Set`` of null-ish sentinels used by
         * the loop below to filter — not a defaults object.
         * Cloning it produced a ``Set`` with extra string keys
         * tacked on, which worked by accident because JS lets
         * you add fields to any object and ``Object.entries``
         * iterates the bag-like properties. Replace with an
         * empty object: same behavior, no per-call clone, no
         * shape confusion.
         */
        const resultSettings = {};
        let bookSettings = book?.settings || {};
        bookSettings = this.setReadRTLInReverse(bookSettings);
        const allSettings = [
          this.globalSettings,
          this.intermediateSettings,
          bookSettings,
        ];

        for (const settings of allSettings) {
          for (const [key, val] of Object.entries(settings)) {
            if (!SETTINGS_NULL_VALUES.has(val)) {
              resultSettings[key] = val;
            }
          }
        }
        ensureNoTwoPageVertical(resultSettings);

        resultSettings.isVertical = VERTICAL_READING_DIRECTIONS.has(
          resultSettings.readingDirection,
        );
        resultSettings.isReadInReverse = REVERSE_READING_DIRECTIONS.has(
          resultSettings.readingDirection,
        );
        resultSettings.fitToClass = this.fitToClass(resultSettings);

        this.bookSettings[book.pk] = resultSettings;
      }

      return this.bookSettings[book.pk];
    },
    bookChangeLocation(direction) {
      let location;
      if (this.isBTT) {
        location = direction === "next" ? "left" : "right";
      } else {
        location = direction === "next" ? "right" : "left";
      }
      return location;
    },
    bookChangeCursorClass(direction) {
      let cursor;
      if (this.activeSettings.isReadInReverse) {
        cursor = direction === "next" ? "up" : "down";
      } else {
        cursor = direction === "next" ? "down" : "up";
      }
      return cursor + "Cursor";
    },
    bookChangeShow(direction) {
      return direction === "prev"
        ? this.books.prev && this.isFirstPage
        : this.books.next && this.isLastPage;
    },
    bookChangeIcon(direction) {
      let isDown = direction === "next";
      if (this.isBTT) {
        isDown = !isDown;
      }
      return isDown ? mdiBookArrowDown : mdiBookArrowUp;
    },
    /*
     * UTIL
     */
    isCoverPage(book, page) {
      return (
        (book.readLtr !== false && page === 0) ||
        (book.readLtr && page === book.maxPage)
      );
    },
    _getRouteParams(book, activePage, direction) {
      const deltaModifier = direction === "prev" ? -1 : 1;
      let delta = 1;
      const bookSettings = this.getBookSettings(book);
      if (
        bookSettings.twoPages &&
        !this.isCoverPage(book, +activePage + deltaModifier)
      ) {
        delta = 2;
      }
      delta = delta * deltaModifier;
      const page = +activePage + delta;

      let routeParams = false;
      if (page >= 0 && page <= book.maxPage) {
        // make current book route
        routeParams = {
          pk: book.pk,
          page,
        };
      }
      return routeParams;
    },
    fitToClass(bookSettings) {
      const classes = {};
      let fitTo;
      fitTo =
        this.clientSettings.scale > SCALE_DEFAULT
          ? "Orig"
          : FIT_TO_CLASSES[bookSettings.fitTo];
      if (fitTo) {
        let fitToClass = "fitTo";
        fitToClass += capitalCase(fitTo);
        if (bookSettings.isVertical) {
          fitToClass += "Vertical";
        } else if (bookSettings.twoPages) {
          fitToClass += "Two";
        }
        classes[fitToClass] = true;
      }
      return classes;
    },
    /*
     * MUTATIONS
     */
    _applyGlobalSettings(updates) {
      // Doing this with $patch breaks reactivity
      this.$patch((state) => {
        state.globalSettings = {
          ...state.globalSettings,
          ...updates,
        };
        state.bookSettings = {};
        state.empty = false;
      });
    },
    toggleToolbars() {
      this.showToolbars = !this.showToolbars;
    },
    setShowToolbars() {
      this.showToolbars = true;
    },
    reset() {
      // HACK because $reset doesn't seem to.
      this.$patch((state) => {
        state.arcs = {};
        state.arc = DEFAULT_ARC;
        state.mtime = 0;
        state.settingsLoaded = false;
        state.books = structuredClone(BOOKS_NULL);
        state.routes = structuredClone(ROUTES_NULL);
        state.bookSettings = {};
        state.intermediateSettings = {};
        state.intermediateInfo = null;
      });
    },
    /*
     * ACTIONS
     */
    _getBookRoutePage(book, isPrev) {
      let bookPage = 0;
      if (
        (isPrev && book.readLtr !== false) ||
        (!isPrev && book.readLtr === false)
      ) {
        const bookSettings = this.getBookSettings(book);

        const bookTwoPagesCorrection = bookSettings.twoPages ? -1 : 0;
        bookPage = book.maxPage + bookTwoPagesCorrection;
      }
      return bookPage;
    },
    _getBookRoute(book, isPrev) {
      if (!book) {
        return false;
      }
      const page = this._getBookRoutePage(book, isPrev);
      return {
        pk: book.pk,
        page,
      };
    },
    _getBookRoutes(prevBook, nextBook) {
      return {
        prev: this._getBookRoute(prevBook, true),
        next: this._getBookRoute(nextBook, false),
      };
    },
    async setRoutesAndBookmarkPage(page) {
      const book = this.books.current;
      this.$patch((state) => {
        state.routes.prev = this._getRouteParams(book, page, "prev");
        state.routes.next = this._getRouteParams(book, page, "next");
      });
      try {
        await this._setBookmarkPage(page);
        this.bookChange = undefined;
      } catch (error) {
        /*
         * Don't revert the local page — the user is reading
         * forward; the bookmark catches up on the next call. But
         * surface the failure to the console rather than letting
         * it become an unhandled rejection: the previous code
         * neither caught nor logged here, so a network blip
         * silently lost the bookmark write.
         */
        console.warn("Bookmark write failed:", error);
      }
    },
    setActivePage(page, reactWithScroll = true) {
      if (page < 0) {
        console.warn("Page out of bounds. Redirecting to 0.");
        return this.routeToPage(0);
      } else if (page > this.books.current.maxPage) {
        console.warn(
          `Page out of bounds. Redirecting to ${this.books.current.maxPage}.`,
        );
        return this.routeToPage(this.books.current.maxPage);
      }
      this.reactWithScroll = Boolean(reactWithScroll);
      this.page = +page;
      this.setRoutesAndBookmarkPage(page);
      if (this.isPagesNotRoutes) {
        const route = { params: { pk: this.books.current.pk, page } };
        const { href } = router.resolve(route);
        globalThis.history.pushState({}, undefined, href);
      } else {
        window.scrollTo(0, 0);
      }
    },
    async loadGlobalSettings() {
      READER_API.getSettings(null, ["g"])
        .then((response) => {
          const data = response.data?.scopes?.g;
          if (data) {
            this._applyGlobalSettings(data);
          }
        })
        .catch(console.error);
    },
    async loadBooks({ params, arc, mtime }) {
      if (!this.settingsLoaded) {
        this.loadGlobalSettings();
      }
      const route = router.currentRoute.value;
      if (!params) {
        params = route.params;
      }
      const pk = params.pk;
      const settings = { arc };
      if (!mtime) {
        mtime = route.query?.ts;
        if (!mtime) {
          mtime = this.mtime;
        }
      }
      // Single-flight: rapid Next-Book clicks abort the previous
      // fetch so its late response can't merge stale book settings
      // over the new book's state.
      const signal = useAbortable("reader:loadBooks");
      try {
        const response = await READER_API.getReaderInfo(pk, settings, mtime, {
          signal,
        });
        const data = response.data;
        const books = data.books;

        // Undefined settings breaks code.
        const allBooks = [books?.prev, books?.current, books?.next];
        for (const book of allBooks) {
          if (book && !book.settings) {
            book.settings = {};
          }
        }
        // Generate routes.
        const routesBooks = this._getBookRoutes(books.prev, books.next);

        this.$patch((state) => {
          state.books = books;
          state.arcs = data.arcs;
          state.arc = data.arc;
          state.routes.prev = this._getRouteParams(
            state.books.current,
            params.page,
            "prev",
          );
          state.routes.next = this._getRouteParams(
            state.books.current,
            params.page,
            "next",
          );
          state.routes.books = routesBooks;
          state.routes.close = data.closeRoute;
          state.empty = false;
          state.mtime = data.mtime;
          state.bookSettings = {};
        });

        // Load all three settings layers for the current comic.
        if (books.current?.pk) {
          this.loadAllSettings(+books.current.pk);
        }
        return true;
      } catch (error) {
        if (isAbortError(error)) return;
        console.debug(error);
        this.empty = true;
      }
    },
    async loadMtimes() {
      const arcs = [];
      for (const [group, arcIdInfos] of Object.entries(this.arcs)) {
        for (const pks of Object.keys(arcIdInfos)) {
          const arc = { group, pks };
          arcs.push(arc);
        }
      }
      if (!arcs.length) {
        // No arcs is a 500 from the mtime api. Use the same
        // ``{ group, pks }`` shape the loop above produces — the
        // earlier ``{ r: "0" }`` was a typo that itself returned
        // 500 from the API, so the fallback never actually worked.
        arcs.push({ group: "r", pks: "0" });
      }
      // Dedup so concurrent callers (websocket fan-out across the
      // browser + reader stores, rapid notifications) share one
      // request. Key on the sorted arc list so distinct arc sets
      // don't collide; same-shape concurrent calls coalesce.
      const dedupKey = `reader:loadMtimes:${arcs
        .map((a) => `${a.group}/${a.pks}`)
        .sort()
        .join(",")}`;
      try {
        const response = await dedupedFetch(dedupKey, () =>
          COMMON_API.getMtime(arcs, {}),
        );
        const newMtime = response.data.maxMtime;
        if (newMtime !== this.mtime) {
          return this.loadBooks({ mtime: newMtime });
        }
        return true;
      } catch (error) {
        console.error(error);
      }
    },
    async _setBookmarkPage(page) {
      const groupParams = { group: "c", ids: [+this.books.current.pk] };
      page = Math.max(Math.min(this.books.current.maxPage, page), 0);
      const updates = { page };
      if (
        this.activeSettings.finishOnLastPage &&
        page >= this.books.current.maxPage
      ) {
        updates["finished"] = true;
      }
      await BROWSER_API.updateGroupBookmarks(groupParams, {}, updates);
    },
    async updateComicSettings(updates) {
      const newBookSettings = {
        ...this.books.current.settings,
        ...updates,
      };
      ensureNoTwoPageVertical(newBookSettings);
      const pk = +this.books.current.pk;
      const payload = {
        ...newBookSettings,
        scope: "c",
        scopePk: pk,
      };
      await READER_API.updateSettings(payload)
        .then(() => {
          this.books.current.settings = newBookSettings;
          this.bookSettings = {};
        })
        .catch(console.error);
    },
    setSettingsClient(updates) {
      this.clientSettings = {
        ...this.clientSettings,
        ...updates,
      };
    },
    async clearComicSettings() {
      const pk = +this.books?.current?.pk;
      if (!pk) return;
      await READER_API.resetSettings({ scope: "c", scopePk: pk })
        .then(() => {
          this.$patch((state) => {
            if (state.books.current) {
              state.books.current.settings = {};
            }
            state.bookSettings = {};
          });
        })
        .catch(console.error);
    },
    _getStoryArcPk() {
      // When browsing by story arc, pass the first arc id for scoped settings.
      if (this.arc?.group === "a" && this.arc?.ids?.length) {
        return this.arc.ids[0];
      }
      return null;
    },
    async loadAllSettings(pk) {
      if (!pk) {
        return;
      }
      const arcGroup = this.arc?.group || "s";
      const storyArcPk = this._getStoryArcPk();
      await READER_API.getSettings(pk, ["g", arcGroup, "c"], storyArcPk)
        .then((response) => {
          const data = response.data;
          const scopes = data.scopes || {};
          const scopeInfo = data.scopeInfo || {};

          // Determine the canonical intermediate scope key.
          const intermediateKey = ["s", "f", "a"].find((k) => k in scopes);

          this.$patch((state) => {
            if (scopes.g) {
              state.globalSettings = {
                ...state.globalSettings,
                ...scopes.g,
              };
            }
            state.intermediateSettings =
              (intermediateKey && scopes[intermediateKey]) || {};
            state.intermediateInfo =
              intermediateKey && scopeInfo[intermediateKey]
                ? {
                    scopeType: intermediateKey,
                    scopePk: scopeInfo[intermediateKey].pk,
                    name: scopeInfo[intermediateKey].name,
                  }
                : null;
            if (scopes.c && state.books.current) {
              state.books.current.settings = scopes.c;
            }
            state.bookSettings = {};
          });
        })
        .catch(console.error);
    },
    async updateIntermediateSettings(updates) {
      if (!this.intermediateInfo) {
        return;
      }
      const newSettings = {
        ...this.intermediateSettings,
        ...updates,
      };
      ensureNoTwoPageVertical(newSettings);
      const payload = {
        ...newSettings,
        scope: this.intermediateInfo.scopeType,
        scopePk: this.intermediateInfo.scopePk,
      };
      await READER_API.updateSettings(payload)
        .then(() => {
          this.$patch((state) => {
            state.intermediateSettings = newSettings;
            state.bookSettings = {};
          });
        })
        .catch(console.error);
    },
    async clearIntermediateSettings() {
      if (!this.intermediateInfo) return;
      await READER_API.resetSettings({
        scope: this.intermediateInfo.scopeType,
        scopePk: this.intermediateInfo.scopePk,
      })
        .then(() => {
          this.$patch((state) => {
            state.intermediateSettings = {};
            state.bookSettings = {};
          });
        })
        .catch(console.error);
    },
    async clearGlobalSettings() {
      await READER_API.resetSettings({ scope: "g" })
        .then((response) => {
          const data = response.data;
          this._applyGlobalSettings(data);
          this.clearComicSettings();
        })
        .catch(console.error);
    },
    async updateGlobalSettings(updates) {
      const newGlobalSettings = {
        ...this.globalSettings,
        ...updates,
      };
      const payload = {
        ...newGlobalSettings,
        scope: "g",
      };
      await READER_API.updateSettings(payload)
        .then((response) => {
          const data = response.data;
          this._applyGlobalSettings(data);
          this.clearComicSettings();
        })
        .catch(console.error);
    },
    setBookChangeFlag(direction) {
      direction = this.normalizeDirection(direction);
      this.bookChange = this.routes.books[direction] ? direction : undefined;
    },
    linkLabel(direction, suffix) {
      const prefix = direction === "prev" ? "Previous" : "Next";
      return `${prefix} ${suffix}`;
    },
    /*
     * ROUTE
     */
    normalizeDirection(direction) {
      return this.activeSettings.isReadInReverse
        ? DIRECTION_REVERSE_MAP[direction]
        : direction;
    },
    _validateRoute(params, book) {
      if (!book) {
        book = this.books.current;
      }
      if (!book) {
        return {};
      }
      const maxPage = book.maxPage ?? 0;
      if (params.page > maxPage) {
        params.page = maxPage;
        console.warn("Tried to navigate past the end of the book.");
      } else if (params.page < 0) {
        params.page = 0;
        console.warn("Tried to navigate before the beginning of the book.");
      }
      return params;
    },
    _routeTo(params, book) {
      params = this._validateRoute(params, book);
      if (this.isPagesNotRoutes && +params.pk === this.books.current.pk) {
        this.setActivePage(+params.page, true);
      } else {
        const route = { name: "reader", params };
        router.push(route).catch(console.debug);
      }
    },
    routeToDirectionOne(direction) {
      // Special two page adjuster
      direction = this.normalizeDirection(direction);
      const delta = direction === "prev" ? -1 : 1;
      const page = (this.page += delta);
      if (page < 0 || page > this.books.current.maxPage) {
        return;
      }
      const params = {
        pk: this.books.current.pk,
        page: page,
      };
      this._routeTo(params);
    },
    routeToDirection(direction) {
      direction = this.normalizeDirection(direction);
      if (this.routes[direction]) {
        const params = this.routes[direction];
        this._routeTo(params);
      } else if (this.routes.books[direction]) {
        if (this.bookChange === direction) {
          this._routeTo(this.routes.books[direction], this.books[direction]);
        } else {
          // Block book change routes unless the book change flag is set.
          this.setBookChangeFlag(direction);
        }
      } else {
        console.debug("No route to direction", direction);
      }
    },
    routeToPage(page) {
      const params = { pk: this.books.current.pk, page };
      this._routeTo(params);
    },
    routeToBook(direction) {
      this._routeTo(this.routes.books[direction], this.books[direction]);
    },
    toRoute(params) {
      return params ? { params } : {};
    },
    // PREFETCH
    _prefetchSrc(params, direction, bookChange = false, secondPage = false) {
      if (!params) {
        return false;
      }
      const book = bookChange ? this.books[direction] : this.books.current;
      if (!book) {
        return false;
      }
      let page = params.page;
      if (secondPage) {
        const settings = this.getBookSettings(book);
        if (!settings.twoPages) {
          return false;
        }
        page += 1;
      }
      if (page > book.maxPage) {
        return false;
      }
      const paramsPlus = { pk: params.pk, page, mtime: book.mtime };
      return getComicPageSource(paramsPlus);
    },
    prefetchLinks(params, direction, bookChange = false) {
      if (!bookChange && this.cacheBook) {
        return {};
      }
      const sources = [
        this._prefetchSrc(params, direction, bookChange, false),
        this._prefetchSrc(params, direction, bookChange, true),
      ];
      const link = [];
      for (const href of sources) {
        if (href) {
          link.push({ ...PREFETCH_LINK, href });
        }
      }
      return { link };
    },
    prefetchBook(book) {
      if (!this.cacheBook || book.fileType == "PDF") {
        return {};
      }
      const pk = book.pk;
      const link = [];
      for (let page = 0; page <= book.maxPage; page++) {
        const params = { pk, page, mtime: book.mtime };
        const href = getComicPageSource(params);
        if (href) {
          link.push({ ...PREFETCH_LINK, href });
        }
      }
      return { link };
    },
  },
});
