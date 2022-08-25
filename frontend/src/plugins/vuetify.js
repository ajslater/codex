import Vue from "vue";
import Vuetify, { VApp, VMain } from "vuetify/lib";

Vue.use(Vuetify, { components: { VApp, VMain } });

export default new Vuetify({
  theme: {
    dark: true,
    options: {
      customProperties: true,
    },
    themes: {
      dark: {
        primary: "#cc7b19",
      },
    },
  },
  icons: {
    iconfont: "mdiSvg",
  },
});
