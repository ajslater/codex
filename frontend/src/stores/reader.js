import { mdiBookArrowDown, mdiBookArrowUp } from "@mdi/js";
import { capitalCase, snakeCase } from "change-case-all";
import deepClone from "deep-clone";
import { defineStore } from "pinia";

import BROWSER_API from "@/api/v3/browser";
import COMMON_API from "@/api/v3/common";
import API, { getComicPageSource } from "@/api/v3/reader";
import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
import READER_CHOICES from "@/choices/reader-choices.json";
import { getFullComicName } from "@/comic-name";
import router from "@/plugins/router";

const NULL_READER_SETTINGS = {
  // Must be null so axios doesn't throw them out when sending.
  fitTo: "",
  twoPages: null,
  readingDirection: "",
  readRtlInReverse: null,
};
Object.freeze(NULL_READER_SETTINGS);
const NULL_CLIENT_SETTINGS = {
  cacheBook: false,
};
Object.freeze(NULL_CLIENT_SETTINGS);

const SETTINGS_NULL_VALUES = new Set(["", null, undefined]);
Object.freeze(SETTINGS_NULL_VALUES);

const DIRECTION_REVERSE_MAP = {
  prev: "next",
  next: "prev",
};
Object.freeze(DIRECTION_REVERSE_MAP);
const PREFETCH_LINK = { rel: "prefetch", as: "image" };
Object.freeze(PREFETCH_LINK);
export const VERTICAL_READING_DIRECTIONS = new Set(["ttb", "btt"]);
Object.freeze(VERTICAL_READING_DIRECTIONS);
export const REVERSE_READING_DIRECTIONS = new Set(["rtl", "btt"]);
Object.freeze(REVERSE_READING_DIRECTIONS);
const OPPOSITE_READING_DIRECTIONS = {
  ltr: "rtl",
  rtl: "ltr",
  ttb: "btt",
  btt: "ttb",
};
Object.freeze(OPPOSITE_READING_DIRECTIONS);
export const SCALE_DEFAULT = 1.0;
const FIT_TO_CHOICES = { S: "Screen", W: "Width", H: "Height", O: "Original" };
Object.freeze(FIT_TO_CHOICES);
const READER_INFO_KEYS = ["breadcrumbs", "show", "topGroup", "filters"];
Object.freeze(READER_INFO_KEYS);
const READER_INFO_ONLY_KEYS = READER_INFO_KEYS.map((key) => snakeCase(key));
Object.freeze(READER_INFO_ONLY_KEYS);
const READER_INFO_SOURCE_KEYS = [...READER_INFO_KEYS, "browserArc"];
Object.freeze(READER_INFO_SOURCE_KEYS);
const BOOKS_NULL = {
  current: undefined,
  prev: false,
  next: false,
};
Object.freeze(BOOKS_NULL);
const ROUTES_NULL = {
  prev: false,
  next: false,
  books: {
    prev: false,
    next: false,
  },
  close: BROWSER_DEFAULTS.breadcrumbs[0],
};
Object.freeze(ROUTES_NULL);

const getGlobalFitToDefault = () => {
  // Big screens default to fit by SCREEN, small to WIDTH;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0,
  );
  return vw > 600 ? "S" : "W";
};

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
      fitTo: READER_CHOICES.fitTo,
      readingDirection: READER_CHOICES.readingDirection,
      nullValues: SETTINGS_NULL_VALUES,
    },

    // server
    readerSettings: {
      fitTo: getGlobalFitToDefault(),
      twoPages: READER_CHOICES.twoPages,
      readingDirection: "ltr",
      readRtlInReverse: READER_CHOICES.readRtlInReverse,
      finishOnLastPage: READER_CHOICES.finishOnLastPage,
    },
    browserSettings: {
      breadcrumbs: BROWSER_DEFAULTS.breadcrumbs,
      show: BROWSER_DEFAULTS.show,
      topGroup: "p",
    },
    books: deepClone(BOOKS_NULL),
    arcs: [],
    arc: {},
    mtime: 0,

    // local reader
    empty: false,
    page: undefined,
    routes: deepClone(ROUTES_NULL),
    bookChange: undefined,
    reactWithScroll: false,
    clientSettings: {
      cacheBook: false,
      scale: SCALE_DEFAULT,
    },
    showToolbars: false,
    settingsLoaded: false,
    bookSettings: {},
  }),
  getters: {
    groupBooks(state) {
      const books = [];
      if (state.books.prev[0]) {
        // eslint-disable-next-line sonarjs/no-unused-expressions
        books.push[state.books.prev[0]];
      }
      // eslint-disable-next-line sonarjs/no-unused-expressions
      books.push[state.books.current];
      if (state.books.next[0]) {
        // eslint-disable-next-line sonarjs/no-unused-expressions
        books.push[state.books.next[0]];
      }
      return books;
    },
    activeSettings(state) {
      // the empty settings guarantee here is for vitest.
      return state.getBookSettings(state.books.current) || {};
    },
    activeTitle(state) {
      const book = state.books.current;
      let title;
      if (book) {
        if (state.arcs[0]?.group != "f") {
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
    cacheBook(state) {
      return (
        state.clientSettings.cacheBook &&
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
      let params = state.routes.close;
      if (params) {
        const cardPk = state.books?.current?.pk;
        if (cardPk) {
          route.hash = `#card-${cardPk}`;
        }
      } else {
        params = window.CODEX.LAST_ROUTE || BROWSER_DEFAULTS.breadcrumbs[0];
      }
      route.params = params;
      return route;
    },
    browserArcFilters(state) {
      const usedFilters = {};
      for (const [key, value] of Object.entries(
        state.browserSettings.filters,
      )) {
        if (key !== "bookmark" && value && value.length > 0) {
          usedFilters[key] = value;
        }
      }
      return usedFilters;
    },
    browserArc(state) {
      const closeRoute = state.routes.close;
      if (closeRoute && closeRoute.pks !== "0") {
        return {
          group: closeRoute.group,
          pks: closeRoute.pks,
          name: closeRoute.name,
          mtime: closeRoute.mtime,
          filters: state.browserArcFilters,
        };
      }
    },
    readerInfoSettings(state) {
      const usedKeys = {};
      for (const key of READER_INFO_SOURCE_KEYS) {
        const value = state.browserSettings[key];
        if (value) {
          usedKeys[key] = value;
        }
      }
      if (state.arc && Object.keys(state.arc).length) {
        usedKeys.arc = {
          group: state.arc.group,
          pks: state.arc.pks,
        };
      } else if (state.browserArc) {
        usedKeys.arc = state.browserArc;
      }
      return usedKeys;
    },
  },
  actions: {
    ///////////////////////////////////////////////////////////////////////////
    // GETTER Algorithms
    setReadRTLInReverse(bookSettings) {
      // Special setting for RTL books
      return this.readerSettings.readRtlInReverse &&
        bookSettings.readingDirection === "rtl"
        ? { ...bookSettings, readingDirection: "ltr" }
        : bookSettings;
    },
    getBookSettings(book) {
      if (!book) {
        return {};
      }
      if (!(book.pk in this.bookSettings)) {
        // Mask the book settings over the global settings.
        const resultSettings = deepClone(SETTINGS_NULL_VALUES);
        let bookSettings = book ? book.settings : {};
        bookSettings = this.setReadRTLInReverse(bookSettings);
        const allSettings = [this.readerSettings, bookSettings];

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
    ///////////////////////////////////////////////////////////////////////////
    // UTIL
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
      if (this.clientSettings.scale > SCALE_DEFAULT) {
        fitTo = "Orig";
      } else {
        fitTo = FIT_TO_CHOICES[bookSettings.fitTo];
      }
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
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    _updateSettings(updates, local) {
      // Doing this with $patch breaks reactivity
      this.$patch((state) => {
        if (local) {
          state.books.current.settings = {
            ...state.books.current.settings,
            ...updates,
          };
          ensureNoTwoPageVertical(state.books.current.settings);
        } else {
          state.readerSettings = {
            ...state.readerSettings,
            ...updates,
          };
        }
        state.bookSettings = {};
      });
    },
    toggleToolbars() {
      this.showToolbars = !this.showToolbars;
    },
    reset() {
      // HACK because $reset doesn't seem to.
      this.$patch((state) => {
        state.arc = undefined;
        state.arcs = [];
        state.mtime = 0;
        state.settingsLoaded = false;
        state.books = deepClone(BOOKS_NULL);
        state.routes = deepClone(ROUTES_NULL);
        state.bookSettings = {};
      });
    },
    ///////////////////////////////////////////////////////////////////////////
    // ACTIONS
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
      await this._setBookmarkPage(page).then(() => {
        this.bookChange = undefined;
        return true;
      });
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
        window.history.pushState({}, undefined, href);
      } else {
        window.scrollTo(0, 0);
      }
    },
    async loadBrowserSettings() {
      return BROWSER_API.getSettings({
        only: READER_INFO_ONLY_KEYS,
        breadcrumbNames: false,
      })
        .then((response) => {
          // Get reader settings before getting books ensures closeRoute.
          // Get browser settings before getting books gets filters & breadcrumbs.
          // Ensures getting the reader arc from breadcrumbs.
          this.$patch((state) => {
            state.browserSettings = response.data;
            if (!state.routes.close && state.browserSettings.breadcrumbs) {
              state.routes.close = state.browserSettings.breadcrumbs.at(-1);
            }
          });
          if (!this.settingsLoaded) {
            this.settingsLoaded = true;
            return this.loadBooks({});
          }
          return true;
        })
        .catch(console.error);
    },
    async loadReaderSettings() {
      API.getReaderSettings()
        .then((response) => {
          const data = response.data;
          this._updateSettings(data, false);
          this.empty = false;
          return this.loadBrowserSettings();
        })
        .catch(console.error);
    },
    async loadBooks({ params, arc, mtime }) {
      if (!this.settingsLoaded) {
        this.loadReaderSettings();
      }
      const route = router.currentRoute.value;
      if (!params) {
        params = route.params;
      }
      const pk = params.pk;
      const settings = this.readerInfoSettings;
      if (arc) {
        settings.arc = arc;
      }
      if (!mtime) {
        mtime = route.query?.ts;
        if (!mtime) {
          mtime = this.mtime;
        }
      }
      await API.getReaderInfo(pk, settings, mtime)
        .then((response) => {
          const data = response.data;
          const books = data.books;

          // Undefined settings breaks code.
          const allBooks = [books?.prevBook, books?.current, books?.nextBook];
          for (const book of allBooks) {
            if (book && !book.settings) {
              book.settings = {};
            }
          }
          // Generate routes.
          const routesBooks = this._getBookRoutes(
            books.prevBook,
            books.nextBook,
          );

          this.$patch((state) => {
            state.books.current = books.current;
            state.books.prev = books.prevBook;
            state.books.next = books.nextBook;
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
          return true;
        })
        .catch((error) => {
          console.debug(error);
          this.empty = true;
        });
    },
    async loadMtimes() {
      return await COMMON_API.getMtime(this.arcs, {})
        .then((response) => {
          const newMtime = response.data.maxMtime;
          if (newMtime !== this.mtime) {
            return this.loadBooks({ mtime: newMtime });
          }
          return true;
        })
        .catch(console.error);
    },
    async _setBookmarkPage(page) {
      const groupParams = { group: "c", ids: [+this.books.current.pk] };
      page = Math.max(Math.min(this.books.current.maxPage, page), 0);
      const updates = { page };
      if (
        this.readerSettings.finishOnLastPage &&
        page >= this.books.current.maxPage
      ) {
        updates["finished"] = true;
      }
      await COMMON_API.updateGroupBookmarks(groupParams, updates);
    },
    async setSettingsLocal(data) {
      this._updateSettings(data, true);

      const groupParams = { group: "c", ids: [+this.books.current.pk] };
      await COMMON_API.updateGroupBookmarks(
        groupParams,
        this.books.current.settings,
      );
    },
    setSettingsClient(updates) {
      this.clientSettings = {
        ...this.clientSettings,
        ...updates,
      };
    },
    async clearSettingsLocal() {
      await this.setSettingsLocal(NULL_READER_SETTINGS);
      this.setSettingsClient(NULL_CLIENT_SETTINGS);
    },
    async setSettingsGlobal(data) {
      this._updateSettings(data, false);
      await API.udpateReaderSettings(this.readerSettings);
      await this.clearSettingsLocal();
    },
    setBookChangeFlag(direction) {
      direction = this.normalizeDirection(direction);
      this.bookChange = this.routes.books[direction] ? direction : undefined;
    },
    linkLabel(direction, suffix) {
      const prefix = direction === "prev" ? "Previous" : "Next";
      return `${prefix} ${suffix}`;
    },
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
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
