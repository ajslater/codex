import js from "@eslint/js";
import eslintPluginComments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginArrayFunc from "eslint-plugin-array-func";
import eslintPluginCompat from "eslint-plugin-compat";
import eslintPluginDepend from "eslint-plugin-depend";
import eslintPluginImport from "eslint-plugin-import";
import eslintPluginJsonc from "eslint-plugin-jsonc";
import eslintPluginMarkdown from "eslint-plugin-markdown";
import eslintPluginNoSecrets from "eslint-plugin-no-secrets";
import eslintPluginNoUnsanitized from "eslint-plugin-no-unsanitized";
import eslintPluginPrettier from "eslint-plugin-prettier";
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

const FLAT_RECOMMENDED = "flat/recommended";

export default [
  {
    ignores: [
      "!.circleci",
      "**/__pycache__/",
      "**/*min.css",
      "**/*min.js",
      "*~",
      ".git/",
      ".mypy_cache/",
      ".pytest_cache/",
      ".ruff_cache/",
      ".venv/",
      "bin/docker/registry.yaml", // breaks prettier plugin idk why
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
  js.configs.recommended,
  eslintPluginArrayFunc.configs.all,
  eslintPluginComments.recommended,
  eslintPluginCompat.configs[FLAT_RECOMMENDED],
  eslintPluginDepend.configs[FLAT_RECOMMENDED],
  eslintPluginImport.flatConfigs.recommended,
  ...eslintPluginJsonc.configs["flat/recommended-with-jsonc"],
  ...eslintPluginMarkdown.configs.recommended,
  eslintPluginNoUnsanitized.configs.recommended,
  eslintPluginPrettierRecommended,
  eslintPluginPromise.configs[FLAT_RECOMMENDED],
  eslintPluginRegexp.configs[FLAT_RECOMMENDED],
  eslintPluginSecurity.configs.recommended,
  eslintPluginSonarjs.configs.recommended,
  ...eslintPluginToml.configs[FLAT_RECOMMENDED],
  ...eslintPluginYml.configs["flat/standard"],
  ...eslintPluginYml.configs["flat/prettier"],
  eslintConfigPrettier, // Best if last
  {
    languageOptions: {
      // eslint-plugin-import sets this to 2018.
      ecmaVersion: "latest",
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
      prettier: eslintPluginPrettier,
      promise: eslintPluginPromise,
      security: eslintPluginSecurity,
      "simple-import-sort": eslintPluginSimpleImportSort,
      toml: eslintPluginToml,
      unicorn: eslintPluginUnicorn,
      yml: eslintPluginYml,
    },
    rules: {
      "array-func/prefer-array-from": "off", // for modern browsers the spread operator, as preferred by unicorn, works fine.
      "depend/ban-dependencies": [
        "error",
        {
          // import-x doesn't work with eslint 9 yet
          allowed: ["eslint-plugin-import"],
        },
      ],
      "max-params": ["warn", 4],
      "no-console": "warn",
      "no-debugger": "warn",
      "no-secrets/no-secrets": "error",
      "prettier/prettier": "warn",
      "security/detect-object-injection": "off",
      "simple-import-sort/exports": "warn",
      "simple-import-sort/imports": "warn",
      "space-before-function-paren": "off",
      "unicorn/filename-case": [
        "error",
        { case: "kebabCase", ignore: [".*.md"] },
      ],
      "unicorn/prefer-node-protocol": "off",
      "unicorn/prevent-abbreviations": "off",
      "unicorn/switch-case-braces": ["warn", "avoid"],
    },
  },
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
      "no-undef": "off",
      "no-unused-vars": "off",
    },
  },
  {
    files: ["**/*.md/*.sh"],
    processor: "markdown/markdown",
    rules: {
      "prettier/prettier": ["error", { parser: "sh" }],
      "sonarjs/no-implicit-global": "off",
    },
  },
  {
    files: ["**/*.md/*.toml", "**/*.toml"],
    rules: {
      "prettier/prettier": ["error", { parser: "toml" }],
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
];
