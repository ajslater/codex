import { useWebSocket } from "@vueuse/core";
import { defineStore } from "pinia";
import { watch } from "vue";

import { WS_URL } from "@/api/v3/notify";
import { messages } from "@/choices/websocket-messages.json";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import { useReaderStore } from "@/stores/reader";
import { store } from "@/stores/store";

const USER_GROUP_ROUTES = Object.freeze([
  "admin-groups",
  "admin-users",
  "admin-libraries",
]);

const HEARTBEAT_INTERVAL_MS = 5_000;
const RECONNECT_RETRIES = Infinity;
const RECONNECT_DELAY_MS = 3_000;

// TODO move to some generic util.
function currentRouteName() {
  return router?.currentRoute?.value?.name;
}

// Manual heartbeat — fire-and-forget empty string, no pong expected.
// VueUse's built-in heartbeat option closes the connection if no pong is
// received within its pongTimeout (default 1000ms), which breaks servers
// that silently consume the ping without echoing anything back.
let heartbeatTimer = 0;

function startHeartbeat(ws) {
  stopHeartbeat();
  heartbeatTimer = globalThis.setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send("");
    }
  }, HEARTBEAT_INTERVAL_MS);
}

function stopHeartbeat() {
  globalThis.clearInterval(heartbeatTimer);
  heartbeatTimer = 0;
}

export const useSocketStore = defineStore("socket", () => {
  const { status, data, open } = useWebSocket(WS_URL, {
    immediate: true,
    autoReconnect: {
      retries: RECONNECT_RETRIES,
      delay: RECONNECT_DELAY_MS,
      onFailed() {
        console.error("[socket] Failed to reconnect after all retries");
      },
    },
    onConnected(ws) {
      startHeartbeat(ws);
      console.debug("[socket] Connected.");
    },
    onError(ws, event) {
      console.error("[socket] Error on", ws.url, event);
    },
    onDisconnected(_ws, event) {
      stopHeartbeat();
      console.debug(
        "[socket] Disconnected with code:",
        event.code,
        "reason:",
        event.reason || "(none)",
      );
    },
  });

  // watch(status, (s) => console.debug("[socket] Status: ", s));

  // Lazy admin store loader

  async function getAdminStore() {
    if (!useAuthStore().isUserAdmin) return undefined;
    return import("@/stores/admin")
      .then((m) => m.useAdminStore())
      .catch(console.error);
  }

  // Notification handlers

  async function adminLoadTables(tables) {
    const adminStore = await getAdminStore();
    adminStore?.loadTables(tables);
  }

  function reloadBrowser() {
    if (currentRouteName() === "browser") {
      useBrowserStore().loadMtimes();
    }
  }

  function adminFlagsNotified() {
    useAuthStore().loadAdminFlags();
    if (currentRouteName() === "admin-flags") {
      adminLoadTables(["Flag"]);
    }
  }

  function groupsNotified() {
    if (USER_GROUP_ROUTES.includes(currentRouteName())) {
      adminLoadTables(["Group"]);
    }
  }

  function usersNotified() {
    if (USER_GROUP_ROUTES.includes(currentRouteName())) {
      adminLoadTables(["User"]);
    }
  }

  async function libraryNotified() {
    useCommonStore().setTimestamp();
    switch (currentRouteName()) {
      case "browser":
        useBrowserStore().loadMtimes();
        break;
      case "reader":
        useReaderStore().loadMtimes();
        break;
      case "admin-libraries":
        adminLoadTables(["Library", "FailedImport"]);
        break;
      case "admin-stats": {
        const adminStore = await getAdminStore();
        adminStore?.loadStats();
        break;
      }
    }
  }

  async function failedImportsNotified() {
    const adminStore = await getAdminStore();
    if (adminStore) adminStore.unseenFailedImports = true;
  }

  // Message Dispatcher

  watch(data, (message) => {
    if (!message) return;
    console.debug("[socket] message:", message);
    switch (message) {
      case messages.ADMIN_FLAGS:
        adminFlagsNotified();
        break;
      case messages.BOOKMARK:
        reloadBrowser();
        break;
      case messages.COVERS:
        reloadBrowser();
        break;
      case messages.GROUPS:
        groupsNotified();
        libraryNotified();
        break;
      case messages.USERS:
        usersNotified();
        libraryNotified();
        break;
      case messages.LIBRARY:
        libraryNotified();
        break;
      case messages.LIBRARIAN_STATUS:
        adminLoadTables(["LibrarianStatus"]);
        break;
      case messages.FAILED_IMPORTS:
        failedImportsNotified();
        break;
      default:
        console.debug("Unhandled WebSocket message:", message);
    }
  });

  // Public open for recconnect when user changes.
  const reopen = () => {
    // Don't force a reopen if we're in the middle of connecting.
    if (status.value == "CONNECTING") return;
    open(true);
  };

  return { reopen };
});

export function useSocketStoreWithOut() {
  return useSocketStore(store);
}
