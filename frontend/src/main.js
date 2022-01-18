import "vuetify/dist/vuetify.min.css"; // Ensure you are using css-loader
import "@mdi/font/css/materialdesignicons.css";

import Vue from "vue";
import VueMeta from "vue-meta";
import VueNativeSock from "vue-native-websocket";
import Vue2Filters from "vue2-filters";

import { SOCKET_URL } from "@/api/v2/notify";
import App from "@/app.vue";
import { SOCKET_OPTIONS } from "@/plugins/vue-native-sock";
import vuetify from "@/plugins/vuetify";
import router from "@/router";
import store from "@/store";

Vue.use(Vue2Filters);
Vue.use(VueMeta, {
  keyName: "head",
});
Vue.use(VueNativeSock, SOCKET_URL, SOCKET_OPTIONS);

const debug = process.env.NODE_ENV !== "production";
Vue.config.performance = debug;

// eslint-disable-next-line no-new
new Vue({
  store,
  router,
  vuetify,
  el: "#App",
  mixins: [Vue2Filters.mixin],
  render: (h) => h(App),
});
