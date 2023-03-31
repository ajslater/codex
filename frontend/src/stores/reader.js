import { defineStore } from "pinia";
import { reactive } from "vue";

import BROWSER_API from "@/api/v3/browser";
import API from "@/api/v3/reader";
import CHOICES from "@/choices";
import { getFullComicName } from "@/comic-name";
import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";

const NULL_READER_SETTINGS = {
  // Must be null so axios doesn't throw them out when sending.
  fitTo: "",
  twoPages: null, // eslint-disable-line unicorn/no-null
  vertical: null, // eslint-disable-line unicorn/no-null
  readInReverse: null, // eslint-disable-line unicorn/no-null
};
Object.freeze(NULL_READER_SETTINGS);

// eslint-disable-next-line unicorn/no-null
const SETTINGS_NULL_VALUES = new Set(["", null, undefined]);
Object.freeze(SETTINGS_NULL_VALUES);

const DIRECTION_REVERSE_MAP = {
  prev: "next",
  next: "prev",
};
Object.freeze(DIRECTION_REVERSE_MAP);

const getGlobalFitToDefault = () => {
  // Big screens default to fit by HEIGHT, small to WIDTH;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0
  );
  return vw > 600 ? "HEIGHT" : "WIDTH";
};

const _scrollToPageRetry = (page, tries = 10, sleep = 0) => {
  // $vuetify.goTo not yet implemented
  // https://vuetifyjs.com/en/features/scrolling/
  // https://github.com/vuetifyjs/vuetify/issues/16471
  const el = document.querySelector(`#page${page}`);
  if (el) {
    el.scrollIntoView();
  } else {
    if (tries > 0) {
      console.log("sleep", sleep);
      setTimeout(function () {
        _scrollToPageRetry(page, tries - 1, sleep + 50);
      }, sleep);
    }
  }
};

export const useReaderStore = defineStore("reader", {
  state: () => ({
    // static
    choices: {
      fitTo: CHOICES.reader.fitTo,
      nullValues: SETTINGS_NULL_VALUES,
    },

    // server
    readerSettings: {
      fitTo: getGlobalFitToDefault(),
      twoPages: false,
      readInReverse: false,
      readRtlInReverse: false,
      vertical: true,
    },
    books: new Map(),
    seriesCount: 0,

    // local reader
    pk: undefined,
    page: undefined,
    routes: {
      prev: false,
      next: false,
      books: {
        prev: false,
        next: false,
      },
    },
    bookChange: undefined,
  }),
  getters: {
    activeBook(state) {
      return state.books.get(state.pk);
    },
    activeSettings(state) {
      return this.getSettings(state.activeBook);
    },
    activeTitle(state) {
      const book = state.activeBook;
      return book ? getFullComicName(book) : "";
    },
    prevBookChangeShow(state) {
      return state.page === 0;
    },
    nextBookChangeShow(state) {
      const maxPage = state.activeBook ? state.activeBook.maxPage : 0;
      const adj =
        state.activeSettings.twoPages && !state.activeSettings.vertical ? 1 : 0;
      const limit = maxPage + adj;
      return state.page >= limit;
    },
    isOnCoverPage(state) {
      return this._isCoverPage(state.activeBook, state.page);
    },
  },
  actions: {
    ///////////////////////////////////////////////////////////////////////////
    // GETTER Algorithms
    getSettings(book) {
      // Mask the book settings over the global settings.
      const bookSettings = book ? book.settings : {};
      const resultSettings = {};
      for (const [key, readerVal] of Object.entries(this.readerSettings)) {
        const bookVal = bookSettings[key];
        const val = SETTINGS_NULL_VALUES.has(bookVal) ? readerVal : bookVal;
        resultSettings[key] = val;
      }
      const bookLtr = book ? book.readLtr : undefined;
      if (
        bookLtr === false &&
        SETTINGS_NULL_VALUES.has(resultSettings.readInReverse)
      ) {
        // special setting for rtl books
        resultSettings.readInReverse = this.readerSettings.readRtlInReverse;
      }
      return resultSettings;
    },
    ///////////////////////////////////////////////////////////////////////////
    // UTIL
    _isCoverPage(book, page) {
      return (
        (book.readLtr !== false && page === 0) ||
        (book.readLtr && page === book.maxPage)
      );
    },
    _numericValues(obj) {
      if (!obj) {
        return obj;
      }
      const res = {};
      for (const [key, val] of Object.entries(obj)) {
        res[key] = +val;
      }
      return res;
    },
    _getRouteParams(activePage, direction) {
      // get possible activeBook page
      const deltaModifier = direction === "prev" ? -1 : 1;
      let delta = 1;
      if (
        this.activeSettings.twoPages &&
        !this._isCoverPage(this.activeBook, +activePage + deltaModifier)
      ) {
        delta = 2;
      }
      delta = delta * deltaModifier;
      const page = +activePage + delta;

      let routeParams = false;
      if (page >= 0 && page <= this.activeBook.maxPage) {
        // make activeBook route
        routeParams = {
          pk: this.pk,
          page,
        };
      }
      return routeParams;
    },
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    _updateSettings(pk, updates) {
      // Doing this with $patch breaks reactivity
      if (pk === 0) {
        this.readerSettings = {
          ...this.readerSettings,
          ...updates,
        };
      } else {
        const book = this.books.get(pk);
        book.settings = {
          ...book.settings,
          ...updates,
        };
      }
    },
    _setRoutes(page) {
      this.$patch((state) => {
        state.routes.prev = this._getRouteParams(page, "prev");
        state.routes.next = this._getRouteParams(page, "next");
      });
    },
    _getBookRoutePage(state, pk, isPrev) {
      const book = state.books.get(pk);

      let bookPage = 0;
      if (
        (isPrev && book.readLtr !== false) ||
        (!isPrev && book.readLtr === false)
      ) {
        const bookSettings = this.getSettings(book);

        const bookTwoPagesCorrection = bookSettings.twoPages ? -1 : 0;
        bookPage = book.maxPage + bookTwoPagesCorrection;
      }
      return bookPage;
    },
    _getBookRoutes(state, prevBookPk, nextBookPk) {
      let prevBookRoute = false;
      if (prevBookPk) {
        const prevBookPage = this._getBookRoutePage(state, prevBookPk, true);
        prevBookRoute = {
          pk: prevBookPk,
          page: prevBookPage,
        };
      }

      let nextBookRoute = false;
      if (nextBookPk) {
        const nextBookPage = this._getBookRoutePage(state, nextBookPk, false);
        nextBookRoute = {
          pk: nextBookPk,
          page: nextBookPage,
        };
      }

      return {
        prev: prevBookRoute,
        next: nextBookRoute,
      };
    },
    setPage(page, scroll = false) {
      this.page = +page;
      if (scroll && this.activeSettings.vertical) {
        this._scrollToPage(this.page);
      }
    },
    ///////////////////////////////////////////////////////////////////////////
    // ACTIONS
    _scrollToPage(page) {
      let el = document.querySelector(`#page${page}`);
      if (el) {
        el.scrollIntoView();
      } else {
        // Get close to the page, wait for the html to appear,
        // And then align it.
        const y = window.innerHeight * page;
        el = document.querySelector("#verticalScroll");
        el.scroll(0, y); // could be ref.scrollToIndex()?
        _scrollToPageRetry(page);
      }
    },
    async setRoutesAndBookmarkPage(page) {
      this._setRoutes(page);
      await this._setBookmarkPage(page).then(() => {
        this.bookChange = undefined;
        return true;
      });
    },
    setActivePage(page, scroll = false) {
      if (page < 0) {
        console.warn("Page out of bounds. Redirecting to 0.");
        return this.routeToPage(0);
      } else if (page > this.activeBook.maxPage) {
        console.warn(
          `Page out of bounds. Redirecting to ${this.activeBook.maxPage}.`
        );
        return this.routeToPage(this.activeBook.maxPage);
      }
      this.setPage(page, scroll);
      this.setRoutesAndBookmarkPage(page);
      if (this.activeSettings.vertical) {
        const route = { params: { pk: this.pk, page } };
        const { href } = router.resolve(route);
        window.history.pushState({}, undefined, href);
      } else {
        window.scrollTo(0, 0);
      }
    },
    async loadReaderSettings() {
      return API.getReaderSettings()
        .then((response) => {
          const data = response.data;
          this._updateSettings(0, data);
          return true;
        })
        .catch(console.error);
    },
    async loadBooks(routeParams) {
      const params = this._numericValues(routeParams);
      await API.getReaderInfo(params.pk)
        .then((response) => {
          const data = response.data;
          let prevBookPk = false;
          let nextBookPk = false;
          this.$patch((state) => {
            const books = new Map();
            for (const [index, book] of data.books.entries()) {
              if (book.pk !== params.pk) {
                if (index === 0) {
                  prevBookPk = book.pk;
                } else {
                  nextBookPk = book.pk;
                }
              }
              // These aren't declared in the state so must
              // have observablitly declared here.
              // For when settings change.
              books.set(book.pk, reactive(book));
            }
            state.books = books;
            state.seriesCount = data.seriesCount;
            state.pk = params.pk;
            state.routes.books = this._getBookRoutes(
              state,
              prevBookPk,
              nextBookPk
            );
          });
          // Would be nice to include this in the above patch
          // but _getRoute needs a lot of computed state.
          this._setRoutes(params.page);
          return true;
        })
        .catch((error) => {
          console.debug(error);
          const page = useBrowserStore().page;
          const route =
            page && page.routes ? page.routes.last : { name: "home" };
          return router.push(route);
        });
    },
    async _setBookmarkPage(page) {
      const groupParams = { group: "c", pk: this.pk };
      page = Math.max(Math.min(this.activeBook.maxPage, page), 0);
      const updates = { page };
      await BROWSER_API.setGroupBookmarks(groupParams, updates);
    },
    async setSettingsLocal(routeParams, data) {
      const params = this._numericValues(routeParams);
      this._updateSettings(params.pk, data);

      await BROWSER_API.setGroupBookmarks(
        {
          group: "c",
          pk: params.pk,
        },
        this.activeBook.settings
      );
    },
    async clearSettingsLocal(routeParams) {
      const params = this._numericValues(routeParams);
      await this.setSettingsLocal(params, NULL_READER_SETTINGS);
    },
    async setSettingsGlobal(routeParams, data) {
      const params = this._numericValues(routeParams);
      this._updateSettings(0, data);
      await API.setReaderSettings(this.readerSettings);
      await this.clearSettingsLocal(params);
    },
    setBookChangeFlag(direction) {
      // direction = this.normalizeDirection(direction);
      this.bookChange = this.routes.books[direction] ? direction : undefined;
    },
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
    normalizeDirection(direction) {
      return this.activeSettings.readInReverse
        ? DIRECTION_REVERSE_MAP[direction]
        : direction;
    },
    _validateRoute(params) {
      const book = this.books.get(params.pk);
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
    _routeTo(params) {
      params = this._validateRoute(params);
      if (this.activeSettings.vertical && +params.pk === this.pk) {
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
      if (page < 0 || page > this.activeBook.maxPage) {
        return;
      }
      const params = {
        pk: this.pk,
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
          this._routeTo(this.routes.books[direction]);
        } else {
          // Block book change routes unless the book change flag is set.
          this.setBookChangeFlag(direction);
        }
      } else {
        console.debug("No route to direction", direction);
      }
    },
    routeToPage(page) {
      const params = { pk: this.pk, page };
      this._routeTo(params);
    },
    routeToBook(direction) {
      this._routeTo(this.routes.books[direction]);
    },
  },
});
