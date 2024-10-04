import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createHead, VueHeadMixin } from "@unhead/vue";
import { createApp } from "vue";
// Exact path fixes eslint-plugin-import
import VueDragScroller from "vue-drag-scroller/dist/vue-drag-scroller.es.js";

// This breaks eslint-plugin-import, could be solved with import assertions
// https://stackoverflow.com/questions/71090960/is-there-a-way-to-make-eslint-understand-the-new-import-assertion-syntax-without
// eslint-disable-next-line
import App from "@/app.vue";
import router from "@/plugins/router";
import { setupNativeSock } from "@/plugins/vue-native-sock";
import vuetify from "@/plugins/vuetify";
import { setupStore } from "@/stores/store";

const app = createApp(App);

app.use(vuetify);
setupStore(app);
setupNativeSock(app);
app.use(router);
app.use(createHead());
app.mixin(VueHeadMixin);
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
