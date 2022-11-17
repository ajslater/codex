// Socket pseudo module for vue-native-sockets
import { defineStore } from "pinia";

import CHOICES from "@/choices";
// import app from "@/main";
import router from "@/plugins/router";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useReaderStore } from "@/stores/reader";
import { store } from "@/stores/store";

const WS_TIMEOUT = 19 * 1000;

// TODO replace with heartHearbeatTimer
// https://github.com/likaia/vue-native-websocket-vue3/blob/master/README-EN.md
const wsKeepAlive = function (ws) {
  if (!ws || ws.readyState !== 1) {
    console.debug("socket not ready, not sending keep-alive.");
    return;
  }
  ws.send("{}");
  setTimeout(() => wsKeepAlive(ws), WS_TIMEOUT);
};

const libraryChanged = function () {
  const browserStore = useBrowserStore();
  const readerStore = useReaderStore();
  browserStore.setTimestamp();
  readerStore.setTimestamp();
  const route = router.currentRoute.value;
  if (route.name === "browser") {
    browserStore.loadBrowserPage({ showProgress: false });
  } else if (route.name == "admin-libraries") {
    useAdminStore().loadTables(["Library", "FailedImport"]);
  }
};

// vue-native-websockets doesn't put socket stuff in its own module :/
export const useSocketStore = defineStore("socket", {
  state: () => ({
    isConnected: false,
    reconnectError: false,
    app: undefined,
  }),
  actions: {
    SOCKET_ONOPEN(event) {
      // const app = getCurrentInstance().appContext;
      this.app.config.globalProperties.$socket = event.currentTarget;
      this.$patch((state) => {
        state.isConnected = true;
        state.reconnectError = false;
      });
      try {
        wsKeepAlive(event.currentTarget);
      } catch (error) {
        // Activating the Vue dev console breaks currentTarget
        console.warn("keep-alive", error);
      }
    },
    SOCKET_ONCLOSE() {
      this.isConnected = false;
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
    sendSubscribe() {
      // const app = getCurrentInstance().appContext;
      const ws = this.app.config.globalProperties.$socket;
      if (!ws || ws.readyState !== 1) {
        console.debug("No ready socket. Not subscribing to notifications.");
        return;
      }
      const authStore = useAuthStore();
      const msg = {
        type: "subscribe",
        register: authStore.isCodexViewable,
        admin: authStore.isUserAdmin,
      };
      ws.send(JSON.stringify(msg));
    },
  },
});

export function useSocketStoreWithOut() {
  return useSocketStore(store);
}
