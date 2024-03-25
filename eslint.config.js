import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import arrayFunc from "eslint-plugin-array-func";
import markdown from "eslint-plugin-markdown";
// import plugin broken for flag config
// https://github.com/import-js/eslint-plugin-import/issues/2556
// import importPlugin from "eslint-plugin-import";
import pluginSecurity from "eslint-plugin-security";
import eslintPluginToml from "eslint-plugin-toml";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import globals from "globals";

const compat = new FlatCompat();

export default [
  {
    languageOptions: {
      globals: {
        ...globals.node,
        ...globals.browser,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    plugins: {
      // import: importPlugin,
      security: pluginSecurity,
      unicorn: eslintPluginUnicorn,
      markdown: markdown,
    },
    rules: {
      "array-func/prefer-array-from": "off", // for modern browsers the spread operator, as preferred by unicorn, works fine.
      "max-params": ["warn", 4],
      "no-console": "warn",
      "no-debugger": "warn",
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "no-secrets/no-secrets": "error",
      "security/detect-object-injection": "off",
      "space-before-function-paren": "off",
      "unicorn/switch-case-braces": ["warn", "avoid"],
      "unicorn/prefer-node-protocol": 0,
      "unicorn/prevent-abbreviations": "off",
      "unicorn/filename-case": [
        "error",
        { case: "kebabCase", ignore: [".*.md"] },
      ],
      /*
     ...importPlugin.configs["recommended"].rules,
     "import/no-unresolved": [
       "error",
       {
         ignore: ["^[@]"],
       },
     ],
     */
    },
    /*
    settings: {
      "import/parsers": {
        espree: [".js", ".cjs", ".mjs", ".jsx"],
        "@typescript-eslint/parser": [".ts"],
      },
      "import/resolver": {
        typescript: true, 
        node: true,
      },
    },
     */
  },
  ...markdown.configs.recommended,
  ...eslintPluginToml.configs["flat/recommended"],
  js.configs.recommended,
  arrayFunc.configs.all,
  {
    files: ["**/*.md"],
    processor: "markdown/markdown",
    rules: {
      "prettier-vue/prettier": ["warn", { parser: "markdown" }],
    },
  },
  {
    files: ["**/*.md/*.js"], // Will match js code inside *.md files
    rules: {
      "no-unused-vars": "off",
      "no-undef": "off",
    },
  },
  {
    files: ["**/*.md/*.sh"],
    rules: {
      "prettier-vue/prettier": ["error", { parser: "sh" }],
    },
  },
  ...compat.config({
    root: true,
    env: {
      browser: true,
      es2024: true,
      node: true,
    },
    extends: [
      // LANGS
      "plugin:jsonc/recommended-with-json",
      "plugin:jsonc/prettier",
      "plugin:yml/standard",
      "plugin:yml/prettier",
      // CODE QUALITY
      "plugin:sonarjs/recommended",
      // PRACTICES
      "plugin:eslint-comments/recommended",
      // "plugin:import/recommended",
      "plugin:no-use-extend-native/recommended",
      "plugin:optimize-regex/all",
      "plugin:promise/recommended",
      "plugin:switch-case/recommended",
      // PRETTIER
      "plugin:prettier-vue/recommended",
      // SECURITY
      "plugin:no-unsanitized/DOM",
    ],
    overrides: [
      {
        files: ["*.yaml", "*.yml"],
        //parser: "yaml-eslint-parser",
        rules: {
          "unicorn/filename-case": "off",
        },
      },
      {
        files: ["*.toml"],
        // parser: "toml-eslint-parser",
        rules: {
          "prettier-vue/prettier": ["error", { parser: "toml" }],
        },
      },
      {
        files: ["*.json", "*.json5", "*.jsonc"],
        parser: "jsonc-eslint-parser",
        //rules: {
        //  "prettier-vue/prettier": ["error", { parser: "json" }],
        //},
      },
      {
        files: ["docker-compose*.yaml"],
        rules: {
          "yml/no-empty-mapping-value": "off",
        },
      },
    ],
    parserOptions: {
      ecmaFeatures: {
        impliedStrict: true,
      },
      ecmaVersion: "latest",
    },
    plugins: [
      "eslint-comments",
      //"import",
      "markdown",
      "no-constructor-bind",
      "no-secrets",
      "no-unsanitized",
      "no-use-extend-native",
      "optimize-regex",
      "prettier-vue",
      "promise",
      "simple-import-sort",
      "sonarjs",
      "switch-case",
      "unicorn",
    ],
    rules: {
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "no-secrets/no-secrets": "error",
      "eslint-comments/no-unused-disable": 1,
      "prettier-vue/prettier": [
        "warn",
        {
          trailingComma: "all",
        },
      ],
      "simple-import-sort/exports": "warn",
      "simple-import-sort/imports": "warn",
      "switch-case/newline-between-switch-case": "off", // Malfunctioning
    },
    ignorePatterns: [
      "*~",
      "**/__pycache__",
      ".git",
      "!.circleci",
      ".mypy_cache",
      ".ruff_cache",
      ".pytest_cache",
      ".venv*",
      "bin/docker/registry.yaml", // breaks prettier plugin idk why
      "cache/*",
      "!cache/packages",
      "cache/packages/*",
      "!cache/packages/README.md",
      "codex/_vendor/",
      "codex/static_build",
      "codex/static_root",
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/**/*.html", // Handled by djlint
      "codex/templates/pwa/serviceworker-register.js", // removes eslint-disable that it then complains about
      "comics",
      "config",
      "dist",
      "frontend",
      "node_modules",
      "package-lock.json",
      "poetry.lock",
      "test-results",
      "typings",
    ],
  }),
];
