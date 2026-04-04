import { defineConfig } from "eslint/config";
import baseConfig from "./cfg/eslint.config.base.js";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVitest from "@vitest/eslint-plugin";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";
import eslintPluginConfigPrettier from "eslint-config-prettier";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig([
  {
    name: "codexIgnores",
    ignores: [
      "codex/_vendor/",
      "codex/static_build/",
      "codex/static/",
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/**/*.html", // Handled by djlint
      "codex/templates/pwa/serviceworker-register.js", // removes eslint-disable that it then complains about
      // "frontend",
    ],
  },
  ...baseConfig,
  ...eslintPluginVue.configs["flat/recommended"].map((c) => ({
    ...c,
    files: ["**/*.vue"],
  })),
  ...eslintPluginVueScopedCSS.configs.all.map((c) => ({
    ...c,
    files: ["**/*.vue"],
  })),
  eslintPluginConfigPrettier, // Again last after adding other plugins.
  {
    files: ["frontend/**/*.{js,vue}"],
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
        alias: { map: [["@", path.resolve(__dirname, "frontend/src")]] },
      },
    },
  },
  {
    files: ["eslint.config.js", "cfg/eslint.config.js"],
    rules: {
      "no-secrets/no-secrets": "off",
    },
  },
  {
    files: ["frontend/src/choices/browser-map.json"],
    rules: { "json/no-empty-keys": "off" },
  },
  { files: ["frontend/tests/**"], ...eslintPluginVitest.configs.recommended },
  {
    files: ["tests/files/comicbox.update.yaml"],
    rules: {
      "yml/no-empty-mapping-value": "off",
    },
  },
]);
