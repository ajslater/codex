import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createHead, VueHeadMixin } from "@unhead/vue/client";
import { createApp } from "vue";
import VueDragScroller from "vue-drag-scroller";

import router from "@/plugins/router";
import vuetify from "@/plugins/vuetify";
import { setupStore } from "@/stores/store";

import App from "@/app.vue";

const app = createApp(App);

app.use(vuetify);
setupStore(app);
app.use(router);
app.use(createHead());
app.mixin(VueHeadMixin);
// App level include fixes not working with mouse left button drag.
app.use(VueDragScroller);

app.config.performance = import.meta.env.PROD;

router
  .isReady()
  .then(() => {
    return app.mount("#App");
  })
  // Top level await would require a plugin

  .catch(console.error);

export default app;
