import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import arrayFunc from "eslint-plugin-array-func";
// import plugin broken for flag config
// https://github.com/import-js/eslint-plugin-import/issues/2556
// import importPlugin from "eslint-plugin-import";
import eslintPluginJsonc from "eslint-plugin-jsonc";
import markdown from "eslint-plugin-markdown";
//import prettier from "eslint-plugin-prettier";
//import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import eslintPluginSecurity from "eslint-plugin-security";
import simpleImportSort from "eslint-plugin-simple-import-sort";
import sonarjs from "eslint-plugin-sonarjs";
import eslintPluginToml from "eslint-plugin-toml";
import unicorn from "eslint-plugin-unicorn";
import eslintPluginYml from "eslint-plugin-yml";
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
      arrayFunc,
      // import: importPlugin,
      markdown,
      // prettier,
      security: eslintPluginSecurity,
      "simple-import-sort": simpleImportSort,
      // sonarjs,
      toml: eslintPluginToml,
      unicorn,
      yml: eslintPluginYml,
    },
    rules: {
      "array-func/prefer-array-from": "off", // for modern browsers the spread operator, as preferred by unicorn, works fine.
      "max-params": ["warn", 4],
      "no-console": "warn",
      "no-debugger": "warn",
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "prettier-vue/prettier": "warn",
      "security/detect-object-injection": "off",
      "simple-import-sort/imports": "warn",
      "simple-import-sort/exports": "warn",
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
    ignores: [
      "!.circleci",
      "**/__pycache__",
      "*test-results*",
      "*~",
      ".git",
      ".mypy_cache",
      ".pytest_cache",
      ".ruff_cache",
      ".venv*",
      "codex/_vendor/",
      "codex/static_build",
      "codex/static_root",
      "codex/templates/**/*.html", // Handled by djlint
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/pwa/serviceworker-register.js", // removes eslint-disable that it then complains about
      "comics",
      "config",
      "dist",
      "frontend",
      "node_modules",
      "package-lock.json",
      "test-results",
      "typings",
    ],
  },
  js.configs.recommended,
  arrayFunc.configs.all,
  ...eslintPluginJsonc.configs["flat/recommended-with-jsonc"],
  ...markdown.configs.recommended,
  //eslintPluginPrettierRecommended,
  //eslintPluginSecurity.configs.recommended,
  sonarjs.configs.recommended,
  ...eslintPluginToml.configs["flat/recommended"],
  ...eslintPluginYml.configs["flat/standard"],
  ...eslintPluginYml.configs["flat/prettier"],
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
  {
    files: ["docker-compose*.yaml"],
    rules: {
      "yml/no-empty-mapping-value": "off",
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
      // PRACTICES
      "plugin:eslint-comments/recommended",
      // "plugin:import/recommended",
      "plugin:no-use-extend-native/recommended",
      "plugin:optimize-regex/all",
      //"plugin:promise/recommended",
      "plugin:switch-case/recommended",
      // PRETTIER
      "plugin:prettier-vue/recommended",
      // SECURITY
      //https://github.com/mozilla/eslint-plugin-no-unsanitized/issues/234
      //"plugin:no-unsanitized/DOM",
    ],
    overrides: [
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
      "no-constructor-bind",
      "no-secrets",
      "no-use-extend-native",
      "optimize-regex",
      "prettier-vue",
      //"promise",
      "switch-case",
    ],
    rules: {
      "eslint-comments/no-unused-disable": 1,
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "no-secrets/no-secrets": "error",
      "prettier-vue/prettier": [
        "warn",
        {
          trailingComma: "all",
        },
      ],
      //"switch-case/newline-between-switch-case": "off", // Malfunctioning
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
