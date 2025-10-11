import eslintPluginVitest from "@vitest/eslint-plugin";
import eslintPluginConfigPrettier from "eslint-config-prettier";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";
import path from "path";
import { fileURLToPath } from "url";
import vueEslintParser from "vue-eslint-parser";

import baseConfig, {
  CONFIGS,
  FLAT_ALL,
  FLAT_RECOMMENDED,
} from "../eslint.config.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default [
  ...baseConfig,
  {
    files: ["**/*.vue"],
    ...CONFIGS.js,
  },
  {
    // Manually config vue plugins.
    files: ["**/*.vue"],
    languageOptions: {
      parser: vueEslintParser,
    },
    plugins: {
      vue: eslintPluginVue,
      vueScopedCSS: eslintPluginVueScopedCSS,
    },
    processor: "vue/vue",
    rules: {
      ...eslintPluginVue.configs["flat/base"].rules,
      ...eslintPluginVue.configs["flat/essential"].rules,
      ...eslintPluginVue.configs["flat/strongly-recommended"].rules,
      ...eslintPluginVue.configs[FLAT_RECOMMENDED].rules,
      ...eslintPluginVueScopedCSS.configs[FLAT_ALL].rules,
    },
  },
  {
    files: ["**/*.js", "**/*.vue"],
    rules: {
      "no-console": [
        "warn",
        { allow: ["clear", "debug", "info", "warn", "error"] },
      ],
      "no-secrets/no-secrets": [
        "error",
        {
          ignoreContent: [
            "notify_groups_changed",
            "notify_failed_imports_changed",
          ],
        },
      ],
    },
    settings: {
      "import/extensions": [".js", ".vue"],
      "import/parsers": {
        "vue-eslint-parser": [".vue"],
        "@eslint/json": [".json"],
      },
      "import/resolver": {
        alias: {
          map: [["@", path.resolve(__dirname, "src")]],
        },
      },
    },
  },
  {
    files: ["src/choices/browser-map.json"],
    rules: {
      "json/no-empty-keys": "off",
    },
  },
  {
    files: ["tests/**"],
    ...eslintPluginVitest.configs.recommended,
  },
  eslintPluginConfigPrettier, // Best if last
];
