import { createVuetify } from "vuetify";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";

const WHITE = "#FFFFFF";
const DISABLED = "#808080";

const codexTheme = {
  dark: true,
  colors: {
    // -- built in ---
    primary: "#CC7B19", // codex orange // '#1976D2' - light blue
    "primary-darken-1": "#965B13",
    // secondary: "#03DAC5", // blue
    // "secondary-darken-1": "#02a191",
    // accent: "#FF4081", // pinkish
    error: "#DC143C", // crimson
    // info: "#2196F3", // lightblue (similar to primary)
    success: "#14dc3c", // crimsongreen
    // warning: "#FB8C00", // soft orange
    "on-surface-variant": "#2A2A2A",
    // --- custom ---
    linkHover: WHITE,
    textPrimary: WHITE,
    textHeader: "#D3D3D3",
    textSecondary: "#A9A9A9",
    textDisabled: DISABLED,
    iconsInactive: DISABLED,
  },
};

export default new createVuetify({
  defaults: {
    global: {
      ripple: true,
    },
    VCheckbox: {
      color: codexTheme.colors.primary,
    },
    VCheckboxBtn: {
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
    VRadioGroup: {
      color: codexTheme.colors.primary,
    },
    VSelect: {
      color: codexTheme.colors.primary,
    },
    VSlider: {
      color: codexTheme.colors.primary,
    },
    VTabs: {
      color: codexTheme.colors.primary,
    },
    VTextField: {
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
