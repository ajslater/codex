import { useWebSocket } from "@vueuse/core";
import { defineStore } from "pinia";

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
// Exponential backoff: 1s, 2s, 4s, 8s, 16s, then 30s cap. Avoids
// hammering a momentarily-down server (the previous fixed 3s delay
// pinned us to ~20 reconnect attempts/min while the server was
// unreachable) while still reconnecting quickly after a transient
// blip. Counter resets on successful connect so a long-lived
// session that drops once doesn't pay the full backoff next time.
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

// TODO move to some generic util.
function currentRouteName() {
  return router?.currentRoute?.value?.name;
}

// Manual heartbeat — fire-and-forget empty string, no pong expected.
// VueUse's built-in heartbeat option closes the connection if no pong is
// received within its pongTimeout (default 1000ms), which breaks servers
// that silently consume the ping without echoing anything back.
let heartbeatTimer = 0;
let reconnectTimer = 0;
let reconnectAttempts = 0;

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

function clearReconnectTimer() {
  globalThis.clearTimeout(reconnectTimer);
  reconnectTimer = 0;
}

function scheduleReconnect(open) {
  // Coalesce: a duplicate ``onDisconnected`` (or a stray error
  // before the scheduled reconnect fires) shouldn't double-schedule.
  if (reconnectTimer) return;
  const delay = Math.min(
    RECONNECT_BASE_MS * 2 ** reconnectAttempts,
    RECONNECT_MAX_MS,
  );
  reconnectAttempts += 1;
  console.debug(
    `[socket] Reconnecting in ${delay}ms (attempt ${reconnectAttempts}).`,
  );
  reconnectTimer = globalThis.setTimeout(() => {
    reconnectTimer = 0;
    open();
  }, delay);
}

export const useSocketStore = defineStore("socket", () => {
  // ``autoReconnect: false`` disables vueuse's fixed-delay loop;
  // we drive reconnect ourselves from ``onDisconnected`` so we can
  // back off exponentially.
  const { status, open } = useWebSocket(WS_URL, {
    immediate: true,
    autoReconnect: false,
    onConnected(ws) {
      clearReconnectTimer();
      reconnectAttempts = 0;
      startHeartbeat(ws);
      console.debug("[socket] Connected.");
    },
    onMessage(_ws, event) {
      dispatchMessage(event.data);
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
      scheduleReconnect(open);
    },
  });

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

  async function adminLoadAllStatuses() {
    const adminStore = await getAdminStore();
    adminStore?.loadAllStatuses();
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

  function dispatchMessage(message) {
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
        useCommonStore().setTimestamp();
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
        adminLoadTables(["ActiveLibrarianStatus"]);
        adminLoadAllStatuses();
        break;
      case messages.FAILED_IMPORTS:
        failedImportsNotified();
        break;
      default:
        console.debug("Unhandled WebSocket message:", message);
    }
  }

  // Public open for recconnect when user changes.
  const reopen = () => {
    // Don't force a reopen if we're in the middle of connecting.
    if (status.value == "CONNECTING") return;
    // Cancel any pending backoff-scheduled reconnect; the user
    // change is an authoritative trigger and we want to attempt
    // immediately, not wait out the previous failure's window.
    clearReconnectTimer();
    reconnectAttempts = 0;
    open(true);
  };

  return { reopen };
});

export function useSocketStoreWithOut() {
  return useSocketStore(store);
}
