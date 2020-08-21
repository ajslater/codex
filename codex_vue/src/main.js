import "./public-path";
import "vuetify/dist/vuetify.min.css"; // Ensure you are using css-loader
import "@mdi/font/css/materialdesignicons.css";

import Vue from "vue";
import Vue2Filters from "vue2-filters";

import App from "@/app.vue";
import vuetify from "@/plugins/vuetify";
import router from "@/router";
import store from "@/store";

Vue.use(Vue2Filters);

new Vue({
  store,
  router,
  vuetify,
  el: "#App",
  mixins: [Vue2Filters.mixin],
  render: (h) => h(App),
});
