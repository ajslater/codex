import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createHead, VueHeadMixin } from "@unhead/vue/client";
import { createApp } from "vue";
import dragScrollDirective from "@/plugins/drag-scroll";

import router from "@/plugins/router";
import vuetify from "@/plugins/vuetify";
import { setupStore } from "@/stores/store";

import App from "@/app.vue";

const app = createApp(App);

app.config.performance = import.meta.env.PROD;

app.use(vuetify);
setupStore(app);
app.use(router);
app.use(createHead());
app.mixin(VueHeadMixin);
app.directive("drag-scroller", dragScrollDirective);

router
  .isReady()
  .then(() => {
    return app.mount("#App");
  })
  // Top level await would require a plugin

  .catch(console.error);

export default app;
