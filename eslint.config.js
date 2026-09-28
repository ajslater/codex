import eslintPluginVitest from "@vitest/eslint-plugin";
import eslintPluginConfigPrettier from "eslint-config-prettier";
import { createNodeResolver } from "eslint-plugin-import-x";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";
import { defineConfig } from "eslint/config";
import path from "node:path";
import { fileURLToPath } from "node:url";

import baseConfig, { SHARED_RULES } from "./cfg/eslint.config.base.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig([
  {
    name: "codexIgnores",
    ignores: [
      "codex/static_build/",
      "codex/static/",
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/**/*.html", // Handled by djlint
      "codex/templates/pwa/serviceworker-register.js", // removes eslint-disable that it then complains about
      "tasks",
      // Manual SSO test harness: authentik blueprints need flow-style
      // custom tags (!Find [...]) and compose needs healthcheck arrays,
      // both of which the yml plugin's block-style rules reject.
      "test-proxy/",
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
    languageOptions: {
      globals: {
        // Injected by vite `define` in frontend/vite.config.js.
        CODEX_PACKAGE_VERSION: "readonly",
      },
    },
    rules: {
      ...SHARED_RULES,
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
            "ForceUpdateConfirmDialog",
          ],
        },
      ],
    },
    settings: {
      // import-x reads only `import-x/*` settings; the old `import/resolver`
      // block named an `alias` resolver that was never installed.
      "import-x/resolver-next": [
        createNodeResolver({
          alias: { "@": [path.resolve(__dirname, "frontend/src")] },
          extensions: [".js", ".json", ".vue"],
        }),
      ],
    },
  },
  {
    // Preset rules that clash with how this codebase is built.
    files: ["**/*.js"],
    name: "codex/style",
    rules: {
      // `const { show: _show, ...query } = settings` strips keys on purpose.
      "no-unused-vars": ["error", { ignoreRestSiblings: true }],
      // Alphabetizing keys would scramble Pinia option stores
      // (state/getters/actions), route tables and the choices maps.
      "perfectionist/sort-objects": "off",
      // The existing style uses `params`, `str`, `e`, `rel` and friends.
      "unicorn/name-replacements": "off",
      // Nulls come from the JSON API and the database and are meaningful.
      "unicorn/no-null": "off",
      // Vue Options API mixins and Pinia option stores use `this`.
      "unicorn/no-this-outside-of-class": "off",
      // Application wiring: app.use(), axios interceptors, vi.mock().
      "unicorn/no-top-level-side-effects": "off",
      // Duplicates no-unused-vars without an ignoreRestSiblings option.
      "sonarjs/no-unused-vars": "off",
      // The code mixes one-line `/** x */` and starred three-line block
      // comments. Both modes of this rule's autofix mangle one of them
      // (dropping the ` * ` gutter or leaving `/* * X */`), the same reason
      // the base config turns off @stylistic/multiline-comment-style.
      "unicorn/single-line-block-comment-style": "off",
    },
  },
  {
    /*
     * Browser code stays runnable on Safari/iOS 15.4, which is all our own
     * code requires (structuredClone, Object.hasOwn, Array#at). The RegExp
     * `v` flag needs Safari 17, and the bundler turns each `v` literal into
     * a RegExp() call that throws on older Safari, several of them at
     * startup. `u` gives these ASCII patterns the same strictness.
     * toSorted/toReversed need Safari 16 and Promise.try 18.2.
     */
    files: ["codex/templates/**/*.js", "frontend/src/**/*.js"],
    name: "codex/browser-floor",
    rules: {
      "regexp/require-unicode-sets-regexp": "off",
      "unicorn/no-array-reverse": "off",
      "unicorn/no-array-sort": "off",
      "unicorn/prefer-promise-try": "off",
    },
  },
  {
    files: ["frontend/tests/**/*.js"],
    name: "codex/tests-style",
    rules: {
      // Tests stub globals (fetch, matchMedia, ...) on purpose.
      "unicorn/no-global-object-property-assignment": "off",
    },
  },
  {
    files: ["eslint.config.js", "cfg/eslint.config.base.js"],
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
