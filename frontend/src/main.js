import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createApp } from "vue";

import App from "@/app.vue";
import router from "@/plugins/router";
import { setupNativeSock } from "@/plugins/vue-native-sock";
import vuetify from "@/plugins/vuetify";
import { setupHead } from "@/plugins/vueuse-head";
import { setupStore } from "@/stores/store";

const app = createApp(App);

app.use(vuetify);
setupHead(app);
setupStore(app);
setupNativeSock(app);
app.use(router);

app.config.performance = import.meta.env.PROD;

router
  .isReady()
  .then(() => {
    return app.mount("#App");
  })
  // Top level await would require a plugin
  // eslint-disable-next-line unicorn/prefer-top-level-await
  .catch(console.error);

export default app;
