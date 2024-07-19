import eslintConfigPrettier from "eslint-config-prettier";
import vitest from "eslint-plugin-vitest";
import pluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";

import baseConfig from "../eslint.config.js";

export default [
  ...baseConfig,
  ...pluginVue.configs["flat/recommended"],
  ...eslintPluginVueScopedCSS.configs["flat/recommended"],
  {
    rules: {
      "no-console": [
        "warn",
        { allow: ["clear", "debug", "info", "warn", "error"] },
      ],
    },
  },
  {
    files: ["tests/**"],
    plugins: {
      vitest,
    },
    rules: {
      ...vitest.configs.recommended.rules,
    },
  },
  eslintConfigPrettier, // Best if last
];
