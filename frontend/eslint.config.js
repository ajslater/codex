import eslintPluginVitest from "@vitest/eslint-plugin";
import eslintPluginConfigPrettier from "eslint-config-prettier";
import { createOxcImportResolver } from "eslint-import-resolver-oxc";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";
import path from "path";
import { fileURLToPath } from "url";
import vueEslintParser from "vue-eslint-parser";

import baseConfig, {
  CONFIGS,
  FLAT_RECOMMENDED,
} from "../cfg/eslint.config.base.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC_PATH = path.resolve(__dirname, "src");

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
      ...eslintPluginVueScopedCSS.configs.all.rules,
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
      "import-x/resolver-next": [
        createOxcImportResolver({
          alias: {
            "@": [SRC_PATH],
          },
        }),
      ],
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
