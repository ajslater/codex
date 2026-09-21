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
    "link-hover": WHITE,
    "text-primary": WHITE,
    "text-header": "#D3D3D3",
    "text-secondary": "#A9A9A9",
    "text-disabled": DISABLED,
    "icons-inactive": DISABLED,
    "include-group": "#141",
    "exclude-group": "#411",
  },
};

/*
 * CSP note: Vuetify injects a runtime <style> tag
 * (id="vuetify-theme-stylesheet") holding the --v-theme-* variables, so
 * the theme needs 'unsafe-inline' in style-src. Turning it off entirely
 * (``theme: false``, and the generated CSS captured into a build-time
 * stylesheet) would not buy anything today: Django already ships
 * style-src 'self' 'unsafe-inline' for Vue's scoped styles. The
 * ``defaults:`` block below sets component prop defaults, not CSS.
 */
const themeDefaults = {
  defaultTheme: "codexTheme",
  themes: {
    codexTheme,
  },
};

const vuetify = createVuetify({
  defaults: {
    global: {
      ripple: true,
    },
    VCheckbox: {
      color: "primary",
    },
    VCheckboxBtn: {
      color: "primary",
    },
    VCombobox: {
      color: "primary",
    },
    VProgressLinear: {
      color: "primary",
    },
    VProgressCircular: {
      color: "primary",
    },
    VRadioGroup: {
      color: "primary",
    },
    VSelect: {
      color: "primary",
    },
    VSlider: {
      color: "primary",
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
      color: "primary",
    },
    VTextField: {
      color: "primary",
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
