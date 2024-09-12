// Socket pseudo module for vue-native-sockets
import { defineStore } from "pinia";

import CHOICES from "@/choices";
import router from "@/plugins/router";
import { useAdminStore } from "@/stores/admin";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";
import { store } from "@/stores/store";

const libraryChanged = function () {
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
      useAdminStore().loadTables(["Library", "FailedImport"]);
      break;
    case "admin-users":
      useAdminStore().loadTables(["User"]);
      break;
    case "admin-groups":
      useAdminStore().loadTables(["Group"]);
      break;
    case "admin-stats":
      useAdminStore().loadStats();
      break;
  }
};

// vue-native-websockets doesn't put socket stuff in its own module :/
export const useSocketStore = defineStore("socket", {
  state: () => ({
    isConnected: false,
    reconnectError: false,
    app: undefined,
    heartBeatInterval: 5 * 1000,
    heartBeatTimer: 0,
  }),
  actions: {
    SOCKET_ONOPEN(event) {
      this.app.config.globalProperties.$socket = event.currentTarget;
      this.$patch((state) => {
        state.isConnected = true;
        state.reconnectError = false;
      });
      this.heartBeatTimer = window.setInterval(() => {
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
      window.clearInterval(this.heartBeatTimer);
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
      // The main message dispatcher.
      // Would be nicer if components could add their own listeners.
      const message = event.data;
      console.debug(message);

      // Cannot instantiate store outside of case blocks.

      switch (message) {
        case CHOICES.websockets.LIBRARY_CHANGED:
          libraryChanged();

          break;
        case CHOICES.websockets.LIBRARIAN_STATUS:
          useAdminStore().loadTable("LibrarianStatus");

          break;
        case CHOICES.websockets.FAILED_IMPORTS:
          useAdminStore().unseenFailedImports = true;

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
  },
});

export function useSocketStoreWithOut() {
  return useSocketStore(store);
}
