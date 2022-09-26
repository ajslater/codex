import { defineStore } from "pinia";

import BROWSER_API from "@/api/v3/browser";
import API from "@/api/v3/reader";
import CHOICES from "@/choices";
import router from "@/router";
import { getFullComicName } from "@/comic-name";

const NULL_READER_SETTINGS = {
  // Must be null so axios doesn't throw them out when sending.
  fitTo: "",
  twoPages: null, // eslint-disable-line unicorn/no-null
};
Object.freeze(NULL_READER_SETTINGS);

// eslint-disable-next-line unicorn/no-null
const SETTINGS_NULL_VALUES = new Set(["", null, undefined]);
Object.freeze(SETTINGS_NULL_VALUES);

const getGlobalFitToDefault = () => {
  // Big screens default to fit by HEIGHT, small to WIDTH;
  const vw = Math.max(
    document.documentElement.clientWidth || 0,
    window.innerWidth || 0
  );
  return vw > 600 ? "HEIGHT" : "WIDTH";
};
const getRouteParams = function (condition, routeParams, increment) {
  // Mutation helper
  return condition
    ? {
        pk: Number(routeParams.pk),
        page: Number(routeParams.page) + increment,
      }
    : false;
};

const isRouteBookChange = function (state, direction) {
  return (
    direction &&
    state.routes &&
    !state.routes[direction] &&
    state.routes[direction + "Book"]
  );
};

const routerPush = function (route) {
  router.push(route).catch((error) => {
    console.debug(error);
  });
};

export const useReaderStore = defineStore("reader", {
  state: () => ({
    choices: {
      // static
      fitTo: CHOICES.reader.fitTo,
    },
    settings: {
      globl: {
        fitTo: getGlobalFitToDefault(),
        twoPages: false,
      },
      local: { ...NULL_READER_SETTINGS },
    },
    timestamp: Date.now(),
    comic: {
      fileFormat: undefined,
      issue: undefined,
      issueSuffix: "",
      issueCount: undefined,
      maxPage: undefined,
      seriesName: "",
      volumeName: "",
    },
    routes: {
      prev: undefined,
      next: undefined,
      prevBook: undefined,
      nextBook: undefined,
      seriesIndex: undefined,
      seriesCount: undefined,
    },
    // LOCAL UI
    bookChange: undefined,
    isSettingsDrawerOpen: false,
    nullValues: SETTINGS_NULL_VALUES,
    comicLoaded: false,
  }),
  getters: {
    computedSettings(state) {
      // Mask the book settings over the global settings.
      const computedSettings = {};
      for (const [key, globalVal] of Object.entries(state.settings.globl)) {
        const localVal = state.settings.local[key];
        const isLocalValSet = !SETTINGS_NULL_VALUES.has(localVal);
        computedSettings[key] = isLocalValSet ? localVal : globalVal;
      }
      return computedSettings;
    },
    fitToClass(state) {
      let classes = {};
      const fitTo = state.computedSettings.fitTo;
      if (fitTo) {
        let fitToClass = "fitTo";
        fitToClass += fitTo.charAt(0).toUpperCase();
        fitToClass += fitTo.slice(1).toLowerCase();
        if (state.computedSettings.twoPages) {
          fitToClass += "Two";
        }
        classes[fitToClass] = true;
      }
      return classes;
    },
    title(state) {
       if (state.comic) {
          return getFullComicName(state.comic);
      }
      return "";
    }
  },
  actions: {
    ///////////////////////////////////////////////////////////////////////////
    // UTIL
    _updateSettings(settingsKey, updates) {
      // Doing this with $patch breaks reactivity
      this.settings[settingsKey] = {
        ...this.settings[settingsKey],
        ...updates,
      };
    },
    ///////////////////////////////////////////////////////////////////////////
    // MUTATIONS
    setBookInfo(data) {
      this.$patch((state) => {
        state.comic = data.comic;
        // Only set prev/next book info do not clobber page routes.
        state.routes.prevBook = data.routes.prevBook;
        state.routes.nextBook = data.routes.nextBook;
        state.routes.seriesIndex = data.routes.seriesIndex;
        state.routes.seriesCount = data.routes.seriesCount;
        state.updatedAt = data.updatedAt;
      });
    },
    setPrevRoute() {
      const routeParams = router.currentRoute.params;
      const condition = Number(routeParams.page) > 0;
      const increment = -1;
      this.routes.prev = getRouteParams(condition, routeParams, increment);
    },
    setNextPage() {
      const routeParams = router.currentRoute.params;
      const twoPages = this.computedSettings.twoPages;
      const increment = twoPages ? 2 : 1;
      const condition =
        Number(routeParams.page) + increment <= this.comic.maxPage;
      this.routes.next = getRouteParams(condition, routeParams, increment);
    },
    setTimestamp() {
      this.timestamp = Date.now();
    },
    ///////////////////////////////////////////////////////////////////////////
    // ACTIONS
    async loadReaderSettings() {
      return API.getReaderSettings()
        .then((response) => {
          const data = response.data;
          this._updateSettings("globl", data);
          return true;
        })
        .catch((error) => {
          return console.error(error);
        });
    },
    async _loadBookSettings() {
      this.comicLoaded = false;
      return API.getComicBookmark(router.currentRoute.params.pk, this.timestamp)
        .then((response) => {
          const data = response.data;
          this._updateSettings("local", data);
          this.comicLoaded = true;
          return this.setRoutesAndBookmarkPage();
        })
        .catch((error) => {
          this.comicLoaded = true;
          return console.error(error);
        });
    },
    async loadBook() {
      await API.getReaderInfo(router.currentRoute.params.pk, this.timestamp)
        .then((response) => {
          const info = response.data;
          this.setBookInfo(info);
          return this._loadBookSettings();
        })
        .catch((error) => {
          if (error.response && [303, 404].includes(error.response.status)) {
            const data = error.response.data;
            console.debug(`redirect: ${data.reason}`);
            const route = { name: "browser", params: data.route };
            return this.routerPush(route);
          } else {
            console.error(error);
          }
        });
    },
    async setBookmarkPage() {
      const pk = +router.currentRoute.params.pk;
      const params = { group: "c", pk };
      const page = +router.currentRoute.params.page;
      const updates = { page };
      await BROWSER_API.setGroupBookmarks(params, updates);
    },
    async setRoutesAndBookmarkPage() {
      this.setPrevRoute();

      this.setNextPage();
      await this.setBookmarkPage().then(() => {
        this.bookChange = undefined;
        return true;
      });
    },
    async setSettingsLocal(data) {
      this._updateSettings("local", data);

      await BROWSER_API.setGroupBookmarks(
        {
          group: "c",
          pk: router.currentRoute.params.pk,
        },
        this.settings.local
      );

      if ("twoPages" in data) {
        this.setNextPage();
      }
    },
    async clearSettingsLocal() {
      await this.setSettingsLocal(NULL_READER_SETTINGS);
    },
    async setSettingsGlobal(data) {
      this._updateSettings("globl", data);
      await API.setReaderSettings(this.settings.globl);
      await this.clearSettingsLocal();
    },
    setBookChangeFlag(direction) {
      this.bookChange = isRouteBookChange(this, direction)
        ? direction
        : undefined;
    },
    ///////////////////////////////////////////////////////////////////////////
    // ROUTE
    routeTo(routeParams) {
      // Validate route
      if (routeParams.pk === router.currentRoute.params.pk) {
        if (routeParams.page > this.comic.maxPage) {
          routeParams.page = this.comic.maxPage;
          console.warn("Tried to navigate past the end of the book.");
        } else if (routeParams.page < 0) {
          routeParams.page = 0;
          console.warn("Tried to navigate before the beginning of the book.");
        }
      }
      const route = { name: "reader", params: routeParams };
      return routerPush(route);
    },
    routeToDirection(direction) {
      if (isRouteBookChange(this, direction) && this.bookChange !== direction) {
        // Block book change routes unless the book change flag is set.
        this.setBookChangeFlag(direction);
        return;
      }
      // Get real route
      const finalRouteParams = this.routes[direction];

      this.routeTo(finalRouteParams);
    },
    routeToPage(page) {
      const params = { pk: Number(router.currentRoute.params.pk), page };
      this.routeTo(params);
    },
  },
});
