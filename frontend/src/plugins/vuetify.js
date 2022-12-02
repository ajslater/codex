import { createVuetify } from "vuetify";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";

const codexTheme = {
  dark: true,
  colors: {
    // -- built in ---
    primary: "#CC7B19", // codex orange // '#1976D2' - light blue
    "primary-darken-1": "#965B13",
    // secondary: "#424242", // grey
    // accent: "#FF4081", // pinkish
    // error: "#FF5252", // soft red
    // info: "#2196F3", // lightblue (similar to primary)
    // success: "#4CAF50", // soft green
    // warning: "#FB8C00", // soft orange
    // --- custom ---
    row: "#272727",
    bookCoverColor: "#000000",
    bookCoverOpacity: 0.55,
    filterSelect: "#1e1e1e",
    highlightOpacity: 0.75,
    linkHover: "#FFFFFF",
    textPrimary: "#FFFFFF",
    textHeader: "#D3D3D3",
    textSecondary: "#A9A9A9",
    textDisabled: "#808080",
    iconsInactive: "#808080",
  },
};

export default new createVuetify({
  defaults: {
    global: {
      ripple: true,
    },
  },
  theme: {
    defaultTheme: "codexTheme",
    options: {
      customProperties: true,
    },
    themes: {
      codexTheme,
    },
  },
  icons: {
    defaultSet: "mdi",
    aliases,
    sets: {
      mdi,
    },
  },
});
