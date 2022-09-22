import { useSocketStore } from "@/stores/socket";

const passToStoreHandler = function (eventName, event) {
  // Pinia shim because vue-native-socket only supports vuex.
  // This method does not run unless this.store is set.
  const target = eventName.toUpperCase();
  const socketStore = this.store();
  if (Object.prototype.hasOwnProperty.call(socketStore, target)) {
    return socketStore[target](event);
  } else {
    console.warn("unhandled socket event", eventName);
  }
};

export const SOCKET_OPTIONS = {
  reconnection: true,
  passToStoreHandler,
  store: useSocketStore,
};

export default {
  SOCKET_OPTIONS,
};
