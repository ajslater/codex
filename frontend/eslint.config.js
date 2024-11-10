import eslintPluginVitest from "@vitest/eslint-plugin";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";
import path from "path";
import { fileURLToPath } from "url";

import baseConfig from "../eslint.config.js";
import { configs, FLAT_BASE, FLAT_RECOMMENDED } from "../eslint.config.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default [
  ...baseConfig,
  {
    files: ["**/*.vue"],
    ...configs.js,
  },
  ...eslintPluginVue.configs[FLAT_BASE],
  {
    files: ["**/*.vue"],
    rules: {
      ...eslintPluginVue.configs[FLAT_RECOMMENDED].rules,
      ...eslintPluginVueScopedCSS.configs[FLAT_RECOMMENDED].rules,
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
    plugins: {
      vitest: eslintPluginVitest,
    },
    rules: {
      ...eslintPluginVitest.configs.recommended.rules,
    },
  },
  eslintConfigPrettier, // Best if last
];
