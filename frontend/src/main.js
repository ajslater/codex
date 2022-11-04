import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createPinia } from "pinia";
import { createApp } from "vue";
import { createMetaManager } from "vue-meta";
import VueNativeSock from "vue-native-websocket-vue3";

import { SOCKET_URL } from "./api/v3/notify";
import App from "./app.vue";
import { SOCKET_OPTIONS } from "./plugins/vue-native-sock";
import vuetify from "./plugins/vuetify";
import router from "./router";

const app = createApp(App);
app.use(vuetify);
const meta = createMetaManager({ keyName: "head" });
app.use(meta);
const pinia = createPinia();
app.use(pinia);
app.use(VueNativeSock, SOCKET_URL, SOCKET_OPTIONS);
app.use(router);

app.config.performance = import.meta.env.PROD;

await router.isReady();
app.mount("#app");
