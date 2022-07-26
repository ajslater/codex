// Socket pseudo module for vue-native-sockets
import CHOICES from "@/choices";
import router from "@/router";

const WS_TIMEOUT = 19 * 1000;
const SUBSCRIBE_MESSAGES = {
  admin: JSON.stringify({
    type: "subscribe",
    register: true,
    admin: true,
  }),
  user: JSON.stringify({ type: "subscribe", register: true }),
  unsub: JSON.stringify({ type: "subscribe", register: false }),
};

const wsKeepAlive = function (ws) {
  if (!ws || ws.readyState !== 1) {
    console.debug("socket not ready, not sending keep-alive.");
    return;
  }
  ws.send("{}");
  setTimeout(() => wsKeepAlive(ws), WS_TIMEOUT);
};

// vue-native-websockets doesn't put socket stuff in its own module :/
const state = {
  isConnected: false,
  isError: false,
};

const mutations = {
  SOCKET_ONOPEN(state, event) {
    state.socket.isConnected = true;
    state.socket.isError = false;
    try {
      wsKeepAlive(event.currentTarget);
    } catch (error) {
      // Activating the Vue dev console breaks currentTarget
      console.warn("keep-alive", error);
    }
  },
  SOCKET_ONCLOSE(state) {
    state.socket.isConnected = false;
  },
  SOCKET_ONERROR(state, event) {
    console.error("socket error", event, state);
    state.socket.isConnected = false;
    state.socket.isError = true;
  },
  SOCKET_ONMESSAGE(state, event) {
    // The main message dispatcher.
    // Would be nicer if components could add their own listeners.
    // 'this' context should be the store.
    const message = event.data;
    console.debug(message);
    switch (message) {
      case CHOICES.websockets.LIBRARY_CHANGED:
        this.commit("browser/setBrowseTimestamp");
        if (router.currentRoute.name === "browser") {
          this.dispatch("browser/getBrowserPage", { showProgress: false });
        }
        this.commit("reader/setTimestamp");
        break;
      case CHOICES.websockets.COVERS_CHANGED:
        this.commit("browser/setCoverTimestamp");
        break;
      case CHOICES.websockets.LIBRARIAN_STATUS:
        this.dispatch("admin/fetchLibrarianStatuses");
        break;
      case CHOICES.websockets.FAILED_IMPORTS:
        this.dispatch("admin/setFailedImports", true);
        break;
      default:
        console.debug("Unhandled websocket message:", message);
    }
  },
  SOCKET_RECONNECT(state, count) {
    console.debug("socket reconnect", state, count);
  },
  SOCKET_RECONNECT_ERROR(state) {
    console.error("socket reconnect error", state);
    state.socket.isError = true;
  },
};

const actions = {
  subscribe({ rootGetters }) {
    const ws = this._vm.$socket;
    if (!ws || ws.readyState !== 1) {
      console.debug("No ready socket. Not subscribing to notifications.");
      return;
    }
    const isAdmin = rootGetters["auth/isAdmin"];
    if (isAdmin) {
      ws.send(SUBSCRIBE_MESSAGES.admin);
      return;
    }
    const isOpenToSee = rootGetters["auth/isOpenToSee"];
    if (isOpenToSee) {
      ws.send(SUBSCRIBE_MESSAGES.user);
      return;
    }
    // else
    ws.send(SUBSCRIBE_MESSAGES.unsub);
  },
};

export default {
  namespaced: true,
  actions,
  state,
  mutations,
};
