import "vuetify/dist/vuetify.min.css"; // Ensure you are using css-loader
import "@mdi/font/css/materialdesignicons.css";

import { createPinia, PiniaVuePlugin } from "pinia";
import Vue from "vue";
import VueMeta from "vue-meta";
import VueNativeSock from "vue-native-websocket";
import VueRouter from "vue-router";
import Vuetify, { VApp, VMain } from "vuetify/lib";

import { SOCKET_URL } from "./api/v3/notify";
import App from "./app.vue";
import { SOCKET_OPTIONS } from "./plugins/vue-native-sock";
import vuetify from "./plugins/vuetify";
import router from "./router";

Vue.use(VueMeta, {
  keyName: "head",
});
Vue.use(PiniaVuePlugin);
const pinia = createPinia();
Vue.use(VueNativeSock, SOCKET_URL, SOCKET_OPTIONS);
Vue.use(VueRouter);
Vue.use(Vuetify, { components: { VApp, VMain } });

Vue.config.performance = import.meta.env.PROD;

new Vue({
  pinia,
  router,
  vuetify,
  el: "#App",
  render: (h) => h(App),
});
