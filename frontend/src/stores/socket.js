// Socket pseudo module for vue-native-sockets
import { defineStore } from "pinia";

import { messages } from "@/choices/websocket-messages.json";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";
import { store } from "@/stores/store";

const libraryChanged = function (adminStore) {
  useCommonStore().setTimestamp();
  useAuthStore().loadAdminFlags();
  const routeName = router?.currentRoute?.value?.name;
  switch (routeName) {
    case "browser":
      useBrowserStore().loadMtimes();
      break;
    case "reader":
      useReaderStore().loadMtimes();
      break;
    case "admin-libraries":
      if (adminStore) {
        adminStore.loadTables(["Library", "FailedImport"]);
      }
      break;
    case "admin-users":
      if (adminStore) {
        adminStore.loadTables(["User"]);
      }
      break;
    case "admin-groups":
      if (adminStore) {
        adminStore.loadTables(["Group"]);
      }
      break;
    case "admin-stats":
      if (adminStore) {
        adminStore.loadStats();
      }
      break;
    case "admin-flags":
      if (adminStore) {
        adminStore.loadTables(["Flag"]);
      }
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
  getters: {
    adminStore() {
      // Only load the admin store if the user is an admin.
      let adminStore;
      if (useAuthStore().isUserAdmin) {
        import("@/stores/admin")
          .then((adminModule) => {
            adminStore = adminModule.useAdminStore();
            return adminStore;
          })
          .catch(console.error);
      }
      return adminStore;
    },
  },
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
        case messages.LIBRARY_CHANGED:
          libraryChanged(this.adminStore);

          break;
        case messages.LIBRARIAN_STATUS:
          if (this.adminStore) {
            this.adminStore.loadTable("LibrarianStatus");
          }

          break;
        case messages.FAILED_IMPORTS:
          if (this.adminStore) {
            this.adminStore.unseenFailedImports = true;
          }

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
