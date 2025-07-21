// Socket pseudo module for vue-native-sockets
import { defineStore } from "pinia";

import { messages } from "@/choices/websocket-messages.json";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";
import { store } from "@/stores/store";

const USER_GROUP_ROUTES = ["admin-groups", "admin-users", "admin-libraries"];
Object.freeze(USER_GROUP_ROUTES);
// vue-native-websockets doesn't put socket stuff in its own module :/
export const useSocketStore = defineStore("socket", {
  state: () => ({
    isConnected: false,
    reconnectError: false,
    app: undefined,
    heartBeatInterval: 5 * 1000,
    heartBeatTimer: 0,
  }),
  getters: {
    async adminStore() {
      // Only load the admin store if the user is an admin.
      if (!useAuthStore().isUserAdmin) {
        return;
      }
      // Returns a promise that must be awaited!
      return import("@/stores/admin")
        .then((adminModule) => {
          return adminModule.useAdminStore();
        })
        .catch(console.error);
    },
  },
  actions: {
    SOCKET_ONOPEN(event) {
      this.app.config.globalProperties.$socket = event.currentTarget;
      this.$patch((state) => {
        state.isConnected = true;
        state.reconnectError = false;
      });
      this.heartBeatTimer = globalThis.setInterval(() => {
        try {
          if (this.isConnected) {
            this.app.config.globalProperties.$socket.send("");
          }
        } catch (error) {
          console.warn("keep-alive", error);
        }
      }, this.heartBeatInterval);
    },
    SOCKET_ONCLOSE() {
      this.isConnected = false;
      globalThis.clearInterval(this.heartBeatTimer);
      this.heartBeatTimer = 0;
    },
    SOCKET_ONERROR(event) {
      console.error("socket error", event);
      this.$patch((state) => {
        state.isConnected = false;
        state.reconnectError = true;
      });
    },
    SOCKET_ONMESSAGE(event) {
      /*
       * The main message dispatcher.
       * Would be nicer if components could add their own listeners.
       */
      const message = event.data;
      console.debug(message);
      switch (message) {
        case messages.ADMIN_FLAGS:
          this.adminFlagsNotified();
          break;
        case messages.BOOKMARK:
          this.bookmarksNotified();
          break;
        case messages.COVERS:
          this.coversNotified();
          break;
        case messages.GROUPS:
          this.groupsNotified();
          this.libraryNotified();
          break;
        case messages.USERS:
          this.usersNotified();
          this.libraryNotified();
          break;
        case messages.LIBRARY:
          this.libraryNotified();
          break;
        case messages.LIBRARIAN_STATUS:
          this.adminLoadTables(["LibrarianStatus"]);
          break;
        case messages.FAILED_IMPORTS:
          this.failedImportsNotified();
          break;
        default:
          console.debug("Unhandled websocket message:", message);
      }
    },
    SOCKET_RECONNECT(count) {
      console.debug("socket reconnect", count);
    },
    SOCKET_RECONNECT_ERROR() {
      console.error("socket reconnect error");
      this.reconnectError = true;
    },
    async adminLoadTables(tables) {
      if (this.adminStore) {
        const adminStore = await this.adminStore;
        adminStore.loadTables(tables);
      }
    },
    adminFlagsNotified() {
      useAuthStore().loadAdminFlags();
      const routeName = router?.currentRoute?.value?.name;
      if (routeName === "admin-flags") {
        this.adminLoadTables(["Flag"]);
      }
    },
    reloadBrowser() {
      const routeName = router?.currentRoute?.value?.name;
      if (routeName === "browser") {
        useBrowserStore().loadMtimes();
      }
    },
    bookmarksNotified() {
      this.reloadBrowser();
    },
    coversNotified() {
      this.reloadBrowser();
    },
    groupsNotified() {
      const routeName = router?.currentRoute?.value?.name;
      if (USER_GROUP_ROUTES.includes(routeName)) {
        this.adminLoadTables(["Group"]);
      }
    },
    usersNotified() {
      const routeName = router?.currentRoute?.value?.name;
      if (USER_GROUP_ROUTES.includes(routeName)) {
        this.adminLoadTables(["User"]);
      }
    },
    async libraryNotified() {
      useCommonStore().setTimestamp();
      const routeName = router?.currentRoute?.value?.name;
      switch (routeName) {
        case "browser":
          useBrowserStore().loadMtimes();
          break;
        case "reader":
          useReaderStore().loadMtimes();
          break;
        case "admin-libraries":
          this.adminLoadTables(["Library", "FailedImport"]);
          break;
        case "admin-stats":
          if (this.adminStore) {
            const adminStore = await this.adminStore;
            adminStore.loadStats();
          }
          break;
      }
    },
    async failedImportsNotified() {
      if (this.adminStore) {
        const adminStore = await this.adminStore;
        adminStore.unseenFailedImports = true;
      }
    },
  },
});

export function useSocketStoreWithOut() {
  return useSocketStore(store);
}
