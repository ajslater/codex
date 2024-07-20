import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginVitest from "eslint-plugin-vitest";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";

import baseConfig from "../eslint.config.js";

export default [
  ...baseConfig,
  ...eslintPluginVue.configs["flat/recommended"],
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
      vitest: eslintPluginVitest,
    },
    rules: {
      ...eslintPluginVitest.configs.recommended.rules,
    },
  },
  eslintConfigPrettier, // Best if last
];
