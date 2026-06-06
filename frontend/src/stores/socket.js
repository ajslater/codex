import { useWebSocket } from "@vueuse/core";
import { defineStore } from "pinia";

import { MESSAGE_TYPES, WS_URL_V4, parseV4Message } from "@/api/v4/notify";
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
/*
 * Exponential backoff: 1s, 2s, 4s, 8s, 16s, then 30s cap. Avoids
 * hammering a momentarily-down server (the previous fixed 3s delay
 * pinned us to ~20 reconnect attempts/min while the server was
 * unreachable) while still reconnecting quickly after a transient
 * blip. Counter resets on successful connect so a long-lived
 * session that drops once doesn't pay the full backoff next time.
 */
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

// TODO move to some generic util.
function currentRouteName() {
  return router?.currentRoute?.value?.name;
}

/*
 * Manual heartbeat — fire-and-forget empty string, no pong expected.
 * VueUse's built-in heartbeat option closes the connection if no pong is
 * received within its pongTimeout (default 1000ms), which breaks servers
 * that silently consume the ping without echoing anything back.
 */
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
  /*
   * Coalesce: a duplicate ``onDisconnected`` (or a stray error
   * before the scheduled reconnect fires) shouldn't double-schedule.
   */
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
  /*
   * ``autoReconnect: false`` disables vueuse's fixed-delay loop;
   * we drive reconnect ourselves from ``onDisconnected`` so we can
   * back off exponentially.
   */
  const { status, open } = useWebSocket(WS_URL_V4, {
    immediate: true,
    autoReconnect: false,
    onConnected(ws) {
      clearReconnectTimer();
      reconnectAttempts = 0;
      startHeartbeat(ws);
      console.debug("[socket] Connected.");
      onlineTagSync();
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
    /*
     * Force-skip the admin store's sticky cache: a websocket
     * fan-out fires precisely because the data changed on the
     * server, so cached state is by definition stale.
     */
    adminStore?.loadTables(tables, { force: true });
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

  /*
   * Skip the ``loadMtimes`` mtime gate and pull a fresh page.
   * ``COVERS`` events fire precisely because a cover row changed; the
   * card data the previous response handed us is stale by definition,
   * and the page mtime aggregate doesn't always observe the right
   * write (e.g. a fresh ``CustomCover`` row that swaps the linked FK).
   * Forcing a fetch with a fresh ``ts`` query sidesteps any
   * server-side cachalot caching too.
   */
  function forceReloadBrowser() {
    if (currentRouteName() !== "browser") return;
    const store = useBrowserStore();
    store.browserPageLoaded = true;
    store.loadBrowserPage(Date.now());
  }

  function adminFlagsNotified() {
    useAuthStore().loadAdminFlags();
    // ``Flag`` rows feed the Settings tab directly and the Users tab
    // via the access / age-rating FlagCard sections. Both rely on the
    // Pinia store list — reload whenever we're on either route.
    const route = currentRouteName();
    if (route === "admin-settings" || route === "admin-users") {
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

  /*
   * ``library.changed`` (and groups/users) only signal that something
   * changed; the browser/reader stores probe the scoped ``/api/v4/mtime``
   * and reload only if the currently-viewed collection actually moved.
   */
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

  async function tagWriteErrorsNotified() {
    const adminStore = await getAdminStore();
    adminStore?.loadTagWriteErrors({ force: true });
  }

  async function onlineTagPromptNotified() {
    if (!useAuthStore().isUserAdmin) return;
    import("@/stores/online-tag")
      .then((m) => m.useOnlineTagStore().onPromptNotification())
      .catch(console.error);
  }

  /*
   * On (re)connect, resync transient online-tagging state so any prompts
   * left pending from a previous run or restart surface without waiting for
   * a fresh notification. Best-effort and admin-only.
   */
  function onlineTagSync() {
    if (!useAuthStore().isUserAdmin) return;
    import("@/stores/online-tag")
      .then((m) => m.useOnlineTagStore().refresh())
      .catch(console.error);
  }

  // Message Dispatcher — routes v4 typed payloads ({type, ...}).

  function dispatchMessage(raw) {
    if (!raw) return;
    const payload = parseV4Message(raw);
    if (!payload) {
      console.debug("[socket] unparseable message:", raw);
      return;
    }
    console.debug("[socket] message:", payload);
    switch (payload.type) {
      case MESSAGE_TYPES.ADMIN_FLAGS_CHANGED:
        adminFlagsNotified();
        break;
      case MESSAGE_TYPES.BOOKMARK_CHANGED:
        reloadBrowser();
        break;
      case MESSAGE_TYPES.COVERS_CHANGED:
        useCommonStore().setTimestamp();
        forceReloadBrowser();
        break;
      case MESSAGE_TYPES.GROUPS_CHANGED:
        groupsNotified();
        libraryNotified();
        break;
      case MESSAGE_TYPES.USERS_CHANGED:
        usersNotified();
        libraryNotified();
        break;
      case MESSAGE_TYPES.LIBRARY_CHANGED:
        libraryNotified();
        break;
      case MESSAGE_TYPES.TASK_PROGRESS:
        adminLoadTables(["ActiveLibrarianStatus"]);
        adminLoadAllStatuses();
        break;
      case MESSAGE_TYPES.FAILED_IMPORTS_CHANGED:
        failedImportsNotified();
        break;
      case MESSAGE_TYPES.TAG_WRITE_ERRORS_CHANGED:
        tagWriteErrorsNotified();
        break;
      case MESSAGE_TYPES.TAG_SESSION_PROMPT:
        onlineTagPromptNotified();
        break;
      default:
        console.debug("Unhandled v4 WebSocket type:", payload.type, payload);
    }
  }

  // Public open for recconnect when user changes.
  const reopen = () => {
    // Don't force a reopen if we're in the middle of connecting.
    if (status.value == "CONNECTING") return;
    /*
     * Cancel any pending backoff-scheduled reconnect; the user
     * change is an authoritative trigger and we want to attempt
     * immediately, not wait out the previous failure's window.
     */
    clearReconnectTimer();
    reconnectAttempts = 0;
    open(true);
  };

  return { reopen };
});

export function useSocketStoreWithOut() {
  return useSocketStore(store);
}
