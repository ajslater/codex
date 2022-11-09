import "@mdi/font/css/materialdesignicons.css";
import "vuetify/styles"; // Global CSS has to be imported

import { createApp } from "vue";
import { createMetaManager } from "vue-meta";

import App from "@/app.vue";
// TODO move router into plugins
import router from "@/plugins/router";
import { setupNativeSock } from "@/plugins/vue-native-sock";
import vuetify from "@/plugins/vuetify";
import { setupStore } from "@/stores/store";

const app = createApp(App);
app.use(vuetify);
const meta = createMetaManager({ keyName: "head" });
app.use(meta);
setupStore(app);
setupNativeSock(app);
app.use(router);

app.config.performance = import.meta.env.PROD;

await router.isReady();
app.mount("#App");

export default app;
