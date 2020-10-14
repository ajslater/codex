import Vue from "vue";
import Vuetify from "vuetify/lib";

Vue.use(Vuetify);

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
