import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginArrayFunc from "eslint-plugin-array-func";
// import plugin broken for flag config
// https://github.com/import-js/eslint-plugin-import/issues/2556
// import importPlugin from "eslint-plugin-import";
import eslintPluginJsonc from "eslint-plugin-jsonc";
import eslintPluginMarkdown from "eslint-plugin-markdown";
import eslintPluginNoSecrets from "eslint-plugin-no-secrets";
//import eslintPluginNoUnsanitized from "eslint-plugin-no-unsanitized";
//import eslintPluginNoUseExtendNative from "eslint-plugin-no-use-extend-native";
import eslintPluginPrettier from "eslint-plugin-prettier";
import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import eslintPluginRegexp from "eslint-plugin-regexp";
import eslintPluginSecurity from "eslint-plugin-security";
import eslintPluginSimpleImportSort from "eslint-plugin-simple-import-sort";
import eslintPluginSonarjs from "eslint-plugin-sonarjs";
import eslintPluginToml from "eslint-plugin-toml";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import eslintPluginYml from "eslint-plugin-yml";
import globals from "globals";

const compat = new FlatCompat();

const ignores = [
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
];

const securityRules = {
  // Adding recommended and then turning off rules does not work.
  "security/detect-buffer-noassert": "warn",
  "security/detect-child-process": "warn",
  "security/detect-disable-mustache-escape": "warn",
  "security/detect-eval-with-expression": "warn",
  "security/detect-new-buffer": "warn",
  "security/detect-no-csrf-before-method-override": "warn",
  "security/detect-non-literal-fs-filename": "warn",
  "security/detect-non-literal-regexp": "warn",
  "security/detect-non-literal-require": "warn",
  //'security/detect-object-injection': 'warn',
  "security/detect-possible-timing-attacks": "warn",
  "security/detect-pseudoRandomBytes": "warn",
  "security/detect-unsafe-regex": "warn",
  "security/detect-bidi-characters": "warn",
};

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
      arrayFunc: eslintPluginArrayFunc,
      jsonc: eslintPluginJsonc,
      markdown: eslintPluginMarkdown,
      "no-secrets": eslintPluginNoSecrets,
      // "no-use-extend-native": eslintPluginNoUseExtendNative,
      // "no-unsantized": eslintPluginNoUnsanitized,
      prettier: eslintPluginPrettier,
      security: eslintPluginSecurity,
      "simple-import-sort": eslintPluginSimpleImportSort,
      toml: eslintPluginToml,
      unicorn: eslintPluginUnicorn,
      yml: eslintPluginYml,
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
    rules: {
      "array-func/prefer-array-from": "off", // for modern browsers the spread operator, as preferred by unicorn, works fine.
      // "import/no-unresolved": ["error", { ignore: ["^[@]"] } ],
      "max-params": ["warn", 4],
      "no-console": "warn",
      "no-debugger": "warn",
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "no-secrets/no-secrets": "error",
      "prettier/prettier": "warn",
      //"security/detect-object-injection": "off",
      ...securityRules,
      "simple-import-sort/exports": "warn",
      "simple-import-sort/imports": "warn",
      "space-before-function-paren": "off",
      "unicorn/switch-case-braces": ["warn", "avoid"],
      "unicorn/prefer-node-protocol": "off",
      "unicorn/prevent-abbreviations": "off",
      "unicorn/filename-case": [
        "error",
        { case: "kebabCase", ignore: [".*.md"] },
      ],
    },
    ignores,
  },
  js.configs.recommended,
  eslintPluginArrayFunc.configs.all,
  //...eslintPluginImportPlugin.configs["recommended"].rules,
  ...eslintPluginJsonc.configs["flat/recommended-with-jsonc"],
  ...eslintPluginMarkdown.configs.recommended,
  //eslintPluginNoUseExtendNative.configs.recommended,
  //eslintPluginNoUnsanitized.configs.recommended,
  eslintPluginRegexp.configs["flat/recommended"],
  //eslintPluginSecurity.configs.recommended,
  eslintPluginSonarjs.configs.recommended,
  ...eslintPluginToml.configs["flat/recommended"],
  ...eslintPluginYml.configs["flat/standard"],
  ...eslintPluginYml.configs["flat/prettier"],
  eslintPluginPrettierRecommended,
  eslintConfigPrettier, // Best if last
  {
    files: ["**/*.md"],
    processor: "markdown/markdown",
    rules: {
      "prettier/prettier": ["warn", { parser: "markdown" }],
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
      "prettier/prettier": ["error", { parser: "sh" }],
    },
  },
  {
    files: ["*.toml"],
    rules: {
      "prettier/prettier": ["error", { parser: "toml" }],
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
      // "plugin:import/recommended",
      // "plugin:promise/recommended",
      // SECURITY
      // https://github.com/mozilla/eslint-plugin-no-unsanitized/issues/234
      //"plugin:no-unsanitized/DOM",
    ],
    overrides: [],
    parserOptions: {
      ecmaFeatures: {
        impliedStrict: true,
      },
      ecmaVersion: "latest",
    },
    plugins: [
      //"import",
      "no-constructor-bind",
      //"promise",
    ],
    rules: {
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
    },
    ignorePatterns: ignores,
  }),
];
