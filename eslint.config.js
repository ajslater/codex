import eslintJs from "@eslint/js";
import eslintJson from "@eslint/json";
import eslintPluginComments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import eslintPluginStylistic from "@stylistic/eslint-plugin";
import { defineConfig } from "eslint/config";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginArrayFunc from "eslint-plugin-array-func";
import eslintPluginCompat from "eslint-plugin-compat";
import eslintPluginDepend from "eslint-plugin-depend";
import eslintPluginImport from "eslint-plugin-import";
import * as eslintPluginMdx from "eslint-plugin-mdx";
import eslintPluginNoSecrets from "eslint-plugin-no-secrets";
import eslintPluginNoUnsanitized from "eslint-plugin-no-unsanitized";
import eslintPluginNoUseExtendNative from "eslint-plugin-no-use-extend-native";
import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import eslintPluginPromise from "eslint-plugin-promise";
import eslintPluginRegexp from "eslint-plugin-regexp";
import eslintPluginSecurity from "eslint-plugin-security";
import eslintPluginSimpleImportSort from "eslint-plugin-simple-import-sort";
import eslintPluginSonarjs from "eslint-plugin-sonarjs";
import eslintPluginToml from "eslint-plugin-toml";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import eslintPluginYml from "eslint-plugin-yml";
import globals from "globals";

export const FLAT_ALL = "flat/all";
export const FLAT_RECOMMENDED = "flat/recommended";

export const CONFIGS = {
  js: {
    ...eslintJs.configs.all,
    ...eslintPluginArrayFunc.configs.all,
    ...eslintPluginComments.recommended,
    ...eslintPluginCompat.configs[FLAT_RECOMMENDED],
    ...eslintPluginDepend.configs[FLAT_RECOMMENDED],
    ...eslintPluginImport.flatConfigs.all,
    ...eslintPluginNoUnsanitized.configs.recommended,
    ...eslintPluginPromise.configs[FLAT_ALL],
    ...eslintPluginRegexp.configs.all,
    ...eslintPluginSonarjs.configs.all,
    ...eslintPluginUnicorn.configs.all,
    plugins: {
      depend: eslintPluginDepend,
      "no-secrets": eslintPluginNoSecrets,
      "simple-import-sort": eslintPluginSimpleImportSort,
      sonarjs: eslintPluginSonarjs,
      unicorn: eslintPluginUnicorn,
    },
    languageOptions: {
      // eslint-plugin-import recommended sets this to 2018.
      ecmaVersion: "latest",
    },
    rules: {
      "@stylistic/multiline-comment-style": "off", // Multiple bugs with this rule
      "max-params": ["warn", 4],
      "no-console": "warn",
      "no-debugger": "warn",
      "no-secrets/no-secrets": "error",
      "security/detect-object-injection": "off",
      "simple-import-sort/exports": "warn",
      "simple-import-sort/imports": "warn",
    },
  },
};
Object.freeze(CONFIGS);

export default defineConfig([
  {
    name: "globalIgnores",
    ignores: [
      "!.circleci",
      "**/*min.css",
      "**/*min.js",
      "**/__pycache__/",
      "**/node_modules/",
      "**/package-lock.json",
      "*~",
      ".git/",
      ".*cache/",
      ".venv/",
      "codex/_vendor/",
      "codex/static_build/",
      "codex/static_root/",
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/**/*.html", // Handled by djlint
      "codex/templates/pwa/serviceworker-register.js", // removes eslint-disable that it then complains about
      "dist/",
      "frontend",
      "test-results/",
      "typings/",
      "uv.lock",
    ],
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
    rules: {
      "prettier/prettier": "warn",
    },
  },
  {
    files: ["**/*.js"],
    ...CONFIGS.js,
  },
  {
    files: ["**/*.json", "**/*.md/*.json"],
    plugins: {
      json: eslintJson,
    },
    ...eslintJson.configs.recommended,
    language: "json/json",
  },
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
  {
    files: ["**/*.{md,mdx}"],
    ...eslintPluginMdx.flat,
    ...eslintPluginMdx.flatCodeBlocks,
    processor: eslintPluginMdx.createRemarkProcessor({
      lintCodeBlocks: true,
    }),
    rules: {
      "no-undef": "off",
      "no-unused-vars": "off",
      "prettier/prettier": ["warn", { parser: "markdown" }],
    },
  },
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
    files: [
      "**/certbot.yaml",
      "**/compose*.yaml",
      "**/docker-compose*.yaml",
      "**/.*_treestamps.yaml",
      "tests/files/comicbox.update.yaml",
    ],
    rules: {
      "yml/no-empty-mapping-value": "off",
    },
  },
  eslintConfigPrettier, // Best if last
]);
