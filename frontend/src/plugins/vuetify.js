import { createVuetify } from "vuetify";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";

import { createCodexRulesPlugin } from "@/plugins/rules";

const WHITE = "#FFFFFF";
const DISABLED = "#808080";

const codexTheme = {
  dark: true,
  colors: {
    // -- built in ---
    primary: "#CC7B19", // codex orange // '#1976D2' - light blue
    "primary-darken-1": "#965B13",
    /*
     * secondary: "#03DAC5", // blue
     * "secondary-darken-1": "#02a191",
     * accent: "#FF4081", // pinkish
     */
    error: "#DC143C", // crimson
    // info: "#2196F3", // lightblue (similar to primary)
    success: "#14dc3c", // crimsongreen
    warning: "#E6BD0D", // amber — version-footer "update available"
    "surface-light": "#2A2A2A",
    // --- custom ---
    linkHover: WHITE,
    textPrimary: WHITE,
    textHeader: "#D3D3D3",
    textSecondary: "#A9A9A9",
    textDisabled: DISABLED,
    iconsInactive: DISABLED,
    includeGroup: "#141",
    excludeGroup: "#411",
  },
};

/*
 * CSP note: this block makes Vuetify inject a runtime <style> tag
 * (id="vuetify-theme-stylesheet") with the --v-theme-* CSS variables,
 * which forces 'unsafe-inline' in the CSP style-src directive. To
 * tighten CSP, capture the generated theme CSS once into a static
 * SCSS/CSS file imported at build time and set
 * ``theme: { isDisabled: true }`` here. The ``defaults:`` block above
 * is fine — it sets component prop defaults, not CSS.
 */
const themeDefaults = {
  defaultTheme: "codexTheme",
  options: {
    customProperties: true,
  },
  themes: {
    codexTheme,
  },
};

const vuetify = new createVuetify({
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
    /*
     * Vuetify's own default is the Material "inverse surface", a light
     * bar in a dark theme. Codex snackbars are page chrome, so an
     * uncolored one matches the app background. Snackbars that pass
     * ``color`` still win, since props beat defaults.
     */
    VSnackbar: {
      color: "background",
    },
    VTabs: {
      color: codexTheme.colors.primary,
    },
    VTextField: {
      color: codexTheme.colors.primary,
    },
  },
  theme: themeDefaults,
  icons: {
    defaultSet: "mdi",
    aliases,
    sets: {
      mdi,
    },
  },
});

/*
 * createVuetify() does not install the rules plugin; it is a separate Vue
 * plugin that needs the locale instance createVuetify() returns. One
 * composite export keeps `app.use(vuetify)` the single install point for
 * src/main.js AND for every unit test that passes this default export in
 * `global.plugins`. Without it an unresolved ["$alias", …] array is silently
 * skipped by Vuetify's validation and the field validates with no rules at
 * all — a green test over a broken form (tests/unit/rules-plugin.test.js
 * guards this).
 */
const rulesPlugin = createCodexRulesPlugin(vuetify.locale);

export default {
  ...vuetify,
  install(app) {
    app.use(vuetify);
    app.use(rulesPlugin);
  },
};
