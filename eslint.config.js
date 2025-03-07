import eslintJs from "@eslint/js";
import eslintJson from "@eslint/json";
import eslintPluginComments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import eslintPluginStylistic from "@stylistic/eslint-plugin";
import eslintPluginConfigPrettier from "eslint-config-prettier";
import eslintPluginArrayFunc from "eslint-plugin-array-func";
import eslintPluginDepend from "eslint-plugin-depend";
import eslintPluginImport from "eslint-plugin-import";
import * as eslintPluginMdx from "eslint-plugin-mdx";
import eslintPluginNoSecrets from "eslint-plugin-no-secrets";
import eslintPluginNoUnsanitized from "eslint-plugin-no-unsanitized";
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
export const FLAT_BASE = "flat/base";
export const FLAT_RECOMMENDED = "flat/recommended";

export const CONFIGS = {
  js: {
    ...eslintJs.configs.recommended,
    ...eslintPluginArrayFunc.configs.all,
    ...eslintPluginComments.recommended,
    ...eslintPluginDepend.configs[FLAT_RECOMMENDED],
    ...eslintPluginImport.flatConfigs.recommended,
    ...eslintPluginNoUnsanitized.configs.recommended,
    ...eslintPluginPromise.configs[FLAT_RECOMMENDED],
    ...eslintPluginRegexp.configs[FLAT_RECOMMENDED],
    ...eslintPluginSonarjs.configs.recommended,
    ...eslintPluginUnicorn.configs.all,
    plugins: {
      depend: eslintPluginDepend,
      "no-secrets": eslintPluginNoSecrets,
      "simple-import-sort": eslintPluginSimpleImportSort,
      sonarjs: eslintPluginSonarjs,
      unicorn: eslintPluginUnicorn,
    },
    languageOptions: {
      // eslint-plugin-import sets this to 2018.
      ecmaVersion: "latest",
    },
    rules: {
      "array-func/prefer-array-from": "off", // for modern browsers the spread operator, as preferred by unicorn, works fine.
      "no-console": "warn",
      "no-debugger": "warn",
      "no-secrets/no-secrets": "error",
      "security/detect-object-injection": "off",
      "unicorn/switch-case-braces": ["warn", "avoid"],
    },
  },
};
Object.freeze(CONFIGS);

export default [
  {
    ignores: [
      "!.circleci",
      "**/__pycache__/",
      "**/*min.css",
      "**/*min.js",
      "**/*.json",
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
      "comics/",
      "config/",
      "dist/",
      "frontend/",
      "node_modules/",
      "package-lock.json",
      "poetry.lock",
      "test-results/",
      "typings/",
    ],
  },
  eslintPluginPrettierRecommended,
  eslintPluginSecurity.configs.recommended,
  eslintPluginStylistic.configs["all-flat"],
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
  ...eslintPluginToml.configs[FLAT_RECOMMENDED],
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
  ...eslintPluginToml.configs[FLAT_BASE],
  {
    files: ["**/*.toml", "**/*.md/*.toml"],
    rules: {
      ...eslintPluginToml.configs[FLAT_RECOMMENDED].rules,
      "prettier/prettier": ["error", { parser: "toml" }],
    },
  },
  ...eslintPluginYml.configs[FLAT_BASE],
  {
    files: ["**/*.yaml", "**/*.yml", "**/*.md/*.yaml"],
    rules: {
      ...eslintPluginYml.configs[FLAT_RECOMMENDED].rules,
      ...eslintPluginYml.configs["flat/prettier"].rules,
      "prettier/prettier": ["error", { parser: "yaml" }],
    },
  },
  {
    files: [
      "**/certbot.yaml",
      "**/docker-compose*.yaml",
      "**/.*_treestamps.yaml",
    ],
    rules: {
      "yml/no-empty-mapping-value": "off",
    },
  },
  eslintPluginConfigPrettier, // Best if last
];
