// Socket psuedo module for vue-native-sockets
import WS_MESSAGES from "@/choices/websocketMessages";

import { NOTIFY_STATES } from "./modules/notify";

const WS_TIMEOUT = 19 * 1000;
const SCAN_MESSAGES = new Set([
  WS_MESSAGES.SCAN_LIBRARY,
  WS_MESSAGES.SCAN_DONE,
  WS_MESSAGES.FAILED_IMPORTS,
]);
const NOTIFY_MAP = {
  [WS_MESSAGES.SCAN_LIBRARY]: NOTIFY_STATES.SCANNING,
  [WS_MESSAGES.SCAN_DONE]: NOTIFY_STATES.OFF,
  [WS_MESSAGES.FAILED_IMPORTS]: NOTIFY_STATES.FAILED,
};

const wsKeepAlive = function (ws) {
  if (!ws || ws.readyState != 1) {
    console.debug("socket not ready, not sending keep-alives.");
    return;
  }
  console.debug("socket keep-alive");
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
    console.debug("socket opened");
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
    console.debug("socket closed");
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
    const msg = event.data;
    console.debug(msg);
    if (msg === WS_MESSAGES.LIBRARY_CHANGED) {
      // browser
      this.dispatch("browser/getBrowserPage", { showProgress: false });
    } else if (SCAN_MESSAGES.has(msg)) {
      // notify
      const notify = NOTIFY_MAP[msg]; // translate message to state.t s
      this.dispatch("notify/setNotify", notify);
    } else {
      console.debug("Unhandled websocket message:", msg);
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
