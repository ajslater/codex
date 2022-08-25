import "vuetify/dist/vuetify.min.css"; // Ensure you are using css-loader
import "@mdi/font/css/materialdesignicons.css";

import Vue from "vue";
import VueMeta from "vue-meta";
import VueNativeSock from "vue-native-websocket";

import { SOCKET_URL } from "./api/v3/notify";
import App from "./app.vue";
import { SOCKET_OPTIONS } from "./plugins/vue-native-sock";
import vuetify from "./plugins/vuetify";
import router from "./router";
import store from "./store";

Vue.use(VueMeta, {
  keyName: "head",
});
Vue.use(VueNativeSock, SOCKET_URL, SOCKET_OPTIONS);

Vue.config.performance = import.meta.env.PROD;

new Vue({
  store,
  router,
  vuetify,
  el: "#App",
  render: (h) => h(App),
});
