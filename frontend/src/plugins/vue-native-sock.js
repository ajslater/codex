import VueNativeSock from "vue-native-websocket-vue3";

import { SOCKET_URL } from "@/api/v3/notify";
import { useSocketStoreWithOut } from "@/stores/socket";

/*
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
*/

export function setupNativeSock(app) {
  const store = useSocketStoreWithOut();
  store.app = app;
  // store.appGlobalProperites = app.config.globalProperties;

  const SOCKET_OPTIONS = {
    store: store,
    reconnection: true,
  };

  app.use(VueNativeSock, SOCKET_URL, SOCKET_OPTIONS);
}
