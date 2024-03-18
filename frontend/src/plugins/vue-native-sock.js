import VueNativeSock from "vue-native-websocket-vue3";

import { SOCKET_URL } from "@/api/v3/notify";
import { useSocketStoreWithOut } from "@/stores/socket";

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
