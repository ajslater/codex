import { FlatCompat } from "@eslint/eslintrc";
import eslintConfigPrettier from "eslint-config-prettier";

import baseConfig from "./../eslint.config.js";

const compat = new FlatCompat();

export default [
  ...baseConfig,
  ...compat.config({
    extends: [
      // VUE
      "plugin:vue/vue3-recommended",
      "plugin:vue-scoped-css/vue3-recommended",
    ],
    parser: "vue-eslint-parser",
    parserOptions: {
      ecmaVersion: "latest",
      ecmaFeatures: {
        impliedStrict: true,
      },
    },
    overrides: [
      {
        files: ["*.json", "*.json5", "*.jsonc"],
        parser: "jsonc-eslint-parser",
        //rules: {
        //  "prettier-vue/prettier": ["error", { parser: "json" }],
        //},
      },
      {
        files: ["tests/**"],
        plugins: ["vitest"],
        extends: ["plugin:vitest/recommended"],
      },
    ],
    plugins: ["vue"],
    ignorePatterns: [
      "coverage",
      "components.d.ts",
      "!frontend",
      "node_modules",
    ],
    settings: {
      "import/resolver": {
        alias: {
          map: [["@", "./src"]],
        },
      },
    },
    rules: {
      "no-console": [
        "warn",
        { allow: ["clear", "debug", "info", "warn", "error"] },
      ],
      "security/detect-object-injection": "off",
    },
  }),
  eslintConfigPrettier,
];
