// Socket pseudo module for vue-native-sockets
import CHOICES from "@/choices";

import { NOTIFY_STATES } from "./modules/notify";

const WS_TIMEOUT = 19 * 1000;
const NOTIFY_MESSAGES = new Set([
  CHOICES.websockets.LIBRARY_UPDATE_IN_PROGRESS,
  CHOICES.websockets.LIBRARY_UPDATE_DONE,
  CHOICES.websockets.FAILED_IMPORTS,
]);
const NOTIFY_MAP = {
  [CHOICES.websockets.LIBRARY_UPDATE_IN_PROGRESS]:
    NOTIFY_STATES.LIBRARY_UPDATING,
  [CHOICES.websockets.LIBRARY_UPDATE_DONE]: NOTIFY_STATES.OFF,
  [CHOICES.websockets.FAILED_IMPORTS]: NOTIFY_STATES.FAILED,
};

const wsKeepAlive = function (ws) {
  if (!ws || ws.readyState != 1) {
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
    if (message === CHOICES.websockets.LIBRARY_CHANGED) {
      // browser
      this.dispatch("browser/browserPageStale", { showProgress: false });
    } else if (NOTIFY_MESSAGES.has(message)) {
      // notify
      const notify = NOTIFY_MAP[message]; // translate message to state.t s
      this.dispatch("notify/notifyChanged", notify);
    } else {
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

export default {
  state,
  mutations,
};
