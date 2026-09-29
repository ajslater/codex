import eslintPluginComments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import eslintJs from "@eslint/js";
import eslintJson from "@eslint/json";
import eslintPluginStylistic from "@stylistic/eslint-plugin";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginCompat from "eslint-plugin-compat";
import eslintPluginDeMorgan from "eslint-plugin-de-morgan";
import eslintPluginDepend from "eslint-plugin-depend";
import eslintPluginHtml from "eslint-plugin-html";
import eslintPluginImport from "eslint-plugin-import-x";
import eslintPluginMath from "eslint-plugin-math";
import * as eslintPluginMdx from "eslint-plugin-mdx";
import eslintPluginNoSecrets from "eslint-plugin-no-secrets";
import eslintPluginNoUnsanitized from "eslint-plugin-no-unsanitized";
import eslintPluginNoUseExtendNative from "eslint-plugin-no-use-extend-native";
import eslintPluginPackageJson from "eslint-plugin-package-json";
import eslintPluginPerfectionist from "eslint-plugin-perfectionist";
import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import eslintPluginPromise from "eslint-plugin-promise";
import eslintPluginRegexp from "eslint-plugin-regexp";
import eslintPluginSecurity from "eslint-plugin-security";
import eslintPluginSonarjs from "eslint-plugin-sonarjs";
import eslintPluginToml from "eslint-plugin-toml";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import eslintPluginYml from "eslint-plugin-yml";
import { defineConfig } from "eslint/config";
import globals from "globals";

export const FLAT_RECOMMENDED = "flat/recommended";

export const SHARED_RULES = {
  "@stylistic/multiline-comment-style": "off",
  "max-params": ["warn", 4],
  "no-console": "warn",
  "no-debugger": "warn",
  "no-secrets/no-secrets": "error",
  "security/detect-object-injection": "off",
  // Duplicates core no-unused-vars, which has the options worth configuring.
  "sonarjs/no-unused-vars": "off",
  // Unicorn's twin of @stylistic/multiline-comment-style. Both of its autofix
  // modes mangle one-line `/** x */` or starred multi-line block comments.
  "unicorn/single-line-block-comment-style": "off",
};

// Presets for JavaScript. Each becomes its own flat-config entry through
// defineConfig's `extends`, so every preset's rules, plugins and
// languageOptions survive. Spreading them into one object made the last spread
// win and silently discarded everything but SHARED_RULES. `extends` also throws
// on an undefined entry, so a preset name that does not exist fails loudly.
export const JS_PRESETS = Object.freeze([
  eslintJs.configs.recommended,
  eslintPluginComments.recommended,
  eslintPluginCompat.configs[FLAT_RECOMMENDED],
  eslintPluginDeMorgan.configs.recommended,
  eslintPluginDepend.configs[FLAT_RECOMMENDED],
  eslintPluginImport.flatConfigs.recommended, // no `all` preset exists
  eslintPluginMath.configs.recommended,
  eslintPluginNoUnsanitized.configs.recommended,
  eslintPluginPerfectionist.configs["recommended-natural"],
  eslintPluginPromise.configs[FLAT_RECOMMENDED], // no `flat/all` preset exists
  eslintPluginRegexp.configs.all,
  eslintPluginSonarjs.configs.recommended, // no `all` preset exists
  eslintPluginUnicorn.configs.recommended, // `all` adds the opinionated tail
]);

export const CONFIGS = Object.freeze({
  js: {
    extends: JS_PRESETS,
    languageOptions: {
      ecmaVersion: "latest",
    },
    name: "devenv/js",
    rules: {
      ...SHARED_RULES,
    },
  },
});

export default defineConfig([
  {
    ignores: [
      "**/*.min.css",
      "**/*.min.js",
      "**/__pycache__/",
      "**/coverage/",
      "**/htmlcov/",
      "**/node_modules/",
      "*~",
      ".claude",
      ".eslintcache",
      ".git/",
      ".*cache/",
      ".venv/",
      "bun.lock",
      "dist/",
      "tasks/",
      "test-results/",
      "typings/",
      "uv.lock",
    ],
    name: "globalIgnores",
  },
  eslintPluginNoUseExtendNative.configs.recommended,
  eslintPluginSecurity.configs.recommended,
  eslintPluginStylistic.configs.all,
  eslintPluginPrettierRecommended,
  {
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    plugins: {
      "no-secrets": eslintPluginNoSecrets,
    },
    rules: {
      "prettier/prettier": "warn",
    },
  },
  {
    files: ["**/*.html"],
    plugins: { html: eslintPluginHtml },
  },
  {
    files: ["**/*.js"],
    ...CONFIGS.js,
  },
  {
    files: ["**/eslint.config*.js"],
    name: "devenv/eslint-config-files",
    rules: {
      // Plugin modules export `configs` both as a property of the default
      // export and by name; reading it off the default export is their
      // documented usage.
      "import-x/no-named-as-default-member": "off",
    },
  },
  {
    files: ["**/*.json", "**/*.md/*.json"],
    plugins: {
      json: eslintJson,
    },
    ...eslintJson.configs.recommended,
    language: "json/json",
  },
  eslintPluginPackageJson.configs.recommended,
  eslintPluginPackageJson.configs.stylistic,
  eslintPluginPackageJson.configs["recommended-publishable"],
  {
    files: ["package.json"],
    languageOptions: {
      parser: "jsonc-eslint-parser",
    },
    plugins: { depend: eslintPluginDepend },
    rules: {
      "depend/ban-dependencies": "error",
    },
  },
  // Markdown is two entries: the files themselves and their fenced code blocks
  // (virtual `README.md/0.js` files). Spreading both presets into one object
  // kept only the code-block `files` glob, so no Markdown was linted at all.
  {
    ...eslintPluginMdx.flat,
    processor: eslintPluginMdx.createRemarkProcessor({
      lintCodeBlocks: true,
    }),
    rules: {
      ...eslintPluginMdx.flat.rules,
      // The remark CLI already reports these, and this rule's autofix rewrites
      // the whole file with remark-stringify, which fights prettier.
      "mdx/remark": "off",
    },
  },
  eslintPluginMdx.flatCodeBlocks,
  ...eslintPluginToml.configs.recommended,
  {
    files: ["**/*.toml", "**/*.md/*.toml"],
    rules: {
      "prettier/prettier": ["error", { parser: "toml" }],
    },
  },
  ...eslintPluginYml.configs.standard,
  ...eslintPluginYml.configs.prettier,
  {
    files: ["**/*.yaml", "**/*.yml", "**/*.md/*.yaml", "**/*.md/*.yml"],
    rules: {
      "prettier/prettier": ["error", { parser: "yaml" }],
    },
  },
  {
    files: ["**/certbot.yaml", "**/compose*.yaml", "**/.*_treestamps.yaml"],
    rules: {
      "yml/no-empty-mapping-value": "off",
    },
  },
  eslintConfigPrettier, // Best if last
]);
