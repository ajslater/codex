import Vue from "vue";
import Vuetify from "vuetify/lib";
import { Touch } from "vuetify/lib/directives";

Vue.use(Vuetify, {
  directives: { Touch },
});

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
