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
    files: ["frontend/tests/**/*.js"],
    name: "codex/tests-style",
    rules: {
      // Tests stub globals (fetch, matchMedia, ...) on purpose.
      "unicorn/no-global-object-property-assignment": "off",
    },
  },
  {
    // Preset rules that fire on existing code. They were inert until the
    // presets in cfg/eslint.config.base.js started applying, so the code was
    // never written against them. Off until it is cleaned up: re-enable one
    // rule at a time and run `make fix`. Counts are from 2026-09-28.
    files: ["**/*.js"],
    name: "codex/pending-cleanup",
    rules: {
      "import-x/no-named-as-default": "off", // 1 hit
      "promise/always-return": "off", // 9 hits
      "promise/param-names": "off", // 1 hit
      "regexp/no-super-linear-move": "off", // 1 hit
      "regexp/prefer-named-capture-group": "off", // 3 hits
      "regexp/require-unicode-regexp": "off", // 20 hits, 17 fixable
      "regexp/require-unicode-sets-regexp": "off", // 20 hits
      "sonarjs/no-floating-point-equality": "off", // 1 hit
      "sonarjs/no-nested-conditional": "off", // 1 hit
      "sonarjs/parameterized-tests": "off", // 1 hit
      "sonarjs/prefer-specific-assertions": "off", // 6 hits
      "sonarjs/super-linear-regex": "off", // 1 hit
      "sonarjs/todo-tag": "off", // 1 hit
      "unicorn/consistent-boolean-name": "off", // 18 hits, 7 fixable
      "unicorn/consistent-function-scoping": "off", // 18 hits
      "unicorn/no-array-callback-reference": "off", // 2 hits
      "unicorn/no-array-reverse": "off", // 1 hit
      "unicorn/no-array-sort": "off", // 10 hits
      "unicorn/no-computed-property-existence-check": "off", // 10 hits
      "unicorn/no-for-each": "off", // 2 hits
      "unicorn/no-invalid-argument-count": "off", // 1 hit
      "unicorn/no-object-as-default-parameter": "off", // 1 hit
      "unicorn/no-return-array-push": "off", // 2 hits
      "unicorn/no-this-assignment": "off", // 1 hit
      "unicorn/no-top-level-assignment-in-function": "off", // 27 hits
      "unicorn/no-unnecessary-global-this": "off", // 17 hits, 8 fixable
      "unicorn/prefer-await": "off", // 149 hits
      "unicorn/prefer-https": "off", // 3 hits, fixable
      "unicorn/prefer-includes-over-repeated-comparisons": "off", // 2 hits
      "unicorn/prefer-iterator-to-array": "off", // 2 hits
      "unicorn/prefer-number-coercion": "off", // 9 hits
      "unicorn/prefer-number-is-safe-integer": "off", // 6 hits
      "unicorn/prefer-promise-try": "off", // 1 hit
      "unicorn/prefer-promise-with-resolvers": "off", // 1 hit
      "unicorn/prefer-scoped-selector": "off", // 5 hits
      "unicorn/prefer-simple-condition-first": "off", // 4 hits
      "unicorn/prefer-top-level-await": "off", // 1 hit
      "unicorn/require-array-sort-compare": "off", // 8 hits
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
