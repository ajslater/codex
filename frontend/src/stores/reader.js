import { defineStore } from "pinia";

// import { reactive } from "vue";
import BROWSER_API from "@/api/v3/browser";
import API, { getComicPageSource } from "@/api/v3/reader";
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
const PREFETCH_LINK = { rel: "prefetch", as: "image" };
Object.freeze(PREFETCH_LINK);

const getGlobalFitToDefault = () => {
  // Big screens default to fit by HEIGHT, small to WIDTH;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0
  );
  return vw > 600 ? "HEIGHT" : "WIDTH";
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
    books: {
      current: undefined,
      prev: false,
      next: false,
    },
    arcs: [],
    arc: {},

    // local reader
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
    reactWithScroll: false,
  }),
  getters: {
    groupBooks(state) {
      const books = [];
      if (state.books.prev[0]) {
        books.push[state.books.prev[0]];
      }
      books.push[state.books.current];
      if (state.books.next[0]) {
        books.push[state.books.next[0]];
      }
      return books;
    },
    activeSettings(state) {
      return this.getSettings(state.books.current);
    },
    activeTitle(state) {
      const book = state.books.current;
      let title;
      if (state.arcs[0]?.group === "f") {
        // this 0 index will break if we start including series
        //  with file group.
        title = book?.filename;
      }
      if (!title) {
        title = book ? getFullComicName(book) : "";
      }
      return title;
    },
    prevBookChangeShow(state) {
      return state.page === 0;
    },
    nextBookChangeShow(state) {
      const maxPage = state.books.current ? state.books.current.maxPage : 0;
      const adj =
        state.activeSettings.twoPages && !state.activeSettings.vertical ? 1 : 0;
      const limit = maxPage + adj;
      return state.page >= limit;
    },
    isOnCoverPage(state) {
      return this._isCoverPage(state.books.current, state.page);
    },
    routeParams(state) {
      return { pk: +state.books.current.pk, page: +state.page };
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
      // No two pages with vertical
      resultSettings.twoPages =
        resultSettings.twoPages && !resultSettings.vertical;
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
    _getRouteParams(book, activePage, direction) {
      const deltaModifier = direction === "prev" ? -1 : 1;
      let delta = 1;
      const settings = this.getSettings(book);
      if (
        settings.twoPages &&
        !this._isCoverPage(book, +activePage + deltaModifier)
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
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    _updateSettings(updates, local) {
      // Doing this with $patch breaks reactivity
      if (local) {
        this.books.current.settings = {
          ...this.books.current.settings,
          ...updates,
        };
      } else {
        this.readerSettings = {
          ...this.readerSettings,
          ...updates,
        };
      }
    },
    ///////////////////////////////////////////////////////////////////////////
    // ACTIONS
    _getBookRoutePage(book, isPrev) {
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
          `Page out of bounds. Redirecting to ${this.books.current.maxPage}.`
        );
        return this.routeToPage(this.books.current.maxPage);
      }
      this.reactWithScroll = Boolean(reactWithScroll);
      this.page = +page;
      this.setRoutesAndBookmarkPage(page);
      if (this.activeSettings.vertical) {
        const route = { params: { pk: this.books.current.pk, page } };
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
          this._updateSettings(data, false);
          return true;
        })
        .catch(console.error);
    },
    async loadBooks(params) {
      await API.getReaderInfo(params)
        .then((response) => {
          const data = response.data;

          // Undefined settings breaks code.
          const allBooks = [
            data.books.prevBook,
            data.books.current,
            data.books.nextBook,
          ];
          for (const book of allBooks) {
            if (book && !book.settings) {
              book.settings = {};
            }
          }
          // Generate routes.
          const routesBooks = this._getBookRoutes(
            data.books.prevBook,
            data.books.nextBook
          );

          this.$patch((state) => {
            state.books.current = data.books.current;
            state.books.prev = data.books.prevBook;
            state.books.next = data.books.nextBook;
            state.arcs = data.arcs;
            state.arc = data.arc;
            state.routes.prev = this._getRouteParams(
              state.books.current,
              params.page,
              "prev"
            );
            state.routes.next = this._getRouteParams(
              state.books.current,
              params.page,
              "next"
            );
            state.routes.books = routesBooks;
          });
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
      const groupParams = { group: "c", pk: this.books.current.pk };
      page = Math.max(Math.min(this.books.current.maxPage, page), 0);
      const updates = { page };
      await BROWSER_API.setGroupBookmarks(groupParams, updates);
    },
    async setSettingsLocal(data) {
      this._updateSettings(data, true);

      await BROWSER_API.setGroupBookmarks(
        {
          group: "c",
          pk: +this.books.current.pk,
        },
        this.books.current.settings
      );
    },
    async clearSettingsLocal() {
      await this.setSettingsLocal(NULL_READER_SETTINGS);
    },
    async setSettingsGlobal(data) {
      this._updateSettings(data, false);
      await API.setReaderSettings(this.readerSettings);
      await this.clearSettingsLocal();
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
      if (
        this.activeSettings.vertical &&
        +params.pk === this.books.current.pk
      ) {
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
        const settings = this.getSettings(book);
        if (!settings.twoPages) {
          return false;
        }
        page += 1;
      }
      if (page > book.maxPage) {
        return false;
      }
      const paramsPlus = { pk: params.pk, page };
      return getComicPageSource(paramsPlus);
    },
    prefetchLinks(params, direction, bookChange = false) {
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
    toRoute(params) {
      return params ? { params } : {};
    },
    linkLabel(direction, suffix) {
      const prefix = direction === "prev" ? "Previous" : "Next";
      return `${prefix} ${suffix}`;
    },
  },
});
