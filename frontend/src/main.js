import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createHead, VueHeadMixin } from "@unhead/vue/client";
import { createApp } from "vue";

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

app.config.performance = import.meta.env.PROD;

router
  .isReady()
  .then(() => {
    return app.mount("#App");
  })
  // Top level await would require a plugin

  .catch(console.error);

export default app;
