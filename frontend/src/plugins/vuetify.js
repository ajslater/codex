import { createVuetify } from "vuetify";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";

const codexTheme = {
  dark: true,
  colors: {
    // -- built in ---
    primary: "#CC7B19", // codex orange // '#1976D2' - light blue
    "primary-darken-1": "#965B13",
    // secondary: "#03DAC5", // blue
    "secondary-darken-1": "#02a191",
    // accent: "#FF4081", // pinkish
    // error: "#CF6679", // very pink
    // info: "#2196F3", // lightblue (similar to primary)
    // success: "#4CAF50", // soft green
    // warning: "#FB8C00", // soft orange
    // --- custom ---
    "surface-dark": "#191919",
    bookCoverColor: "#000000",
    bookCoverOpacity: 0.55,
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
    VTabs: {
      color: codexTheme.colors.primary,
    },
    VCheckbox: {
      color: codexTheme.colors.primary,
    },
    VCheckboxBtn: {
      color: codexTheme.colors.primary,
    },
    VTextField: {
      color: codexTheme.colors.primary,
    },
    VRadio: {
      color: codexTheme.colors.primary,
    },
    VSelect: {
      color: codexTheme.colors.primary,
    },
    VCombobox: {
      color: codexTheme.colors.primary,
    },
    VProgressLinear: {
      color: codexTheme.colors.primary,
    },
    VProgressCircular: {
      color: codexTheme.colors.primary,
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
