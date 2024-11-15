import eslintJs from "@eslint/js";
import eslintMarkdown from "@eslint/markdown";
import eslintPluginComments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginArrayFunc from "eslint-plugin-array-func";
import eslintPluginCompat from "eslint-plugin-compat";
import eslintPluginDepend from "eslint-plugin-depend";
import eslintPluginImport from "eslint-plugin-import";
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

export const FLAT_RECOMMENDED = "flat/recommended";

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
  eslintJs.configs.recommended,
  eslintPluginArrayFunc.configs.all,
  eslintPluginComments.recommended,
  eslintPluginCompat.configs[FLAT_RECOMMENDED],
  eslintPluginDepend.configs[FLAT_RECOMMENDED],
  eslintPluginImport.flatConfigs.recommended,
  eslintPluginNoUnsanitized.configs.recommended,
  eslintPluginPromise.configs[FLAT_RECOMMENDED],
  eslintPluginRegexp.configs[FLAT_RECOMMENDED],
  eslintPluginSecurity.configs.recommended,
  eslintPluginSonarjs.configs.recommended,
  eslintPluginUnicorn.configs[FLAT_RECOMMENDED],
  eslintPluginPrettierRecommended,
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
      "no-secrets": eslintPluginNoSecrets,
      "simple-import-sort": eslintPluginSimpleImportSort,
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
    files: ["*.md", "**/*.md"],
    language: "markdown/gfm",
    plugins: { markdown: eslintMarkdown },
    processor: "markdown/markdown",
    rules: {
      ...eslintMarkdown.configs.recommended.rules,
      "no-undef": "off",
      "no-unused-vars": "off",
      "prettier/prettier": ["warn", { parser: "markdown" }],
    },
  },
  ...eslintPluginToml.configs[FLAT_RECOMMENDED],
  {
    files: ["*.toml", "**/*.toml"],
    rules: {
      "prettier/prettier": ["error", { parser: "toml" }],
    },
  },
  ...eslintPluginYml.configs[FLAT_RECOMMENDED],
  ...eslintPluginYml.configs["flat/prettier"],
  {
    files: ["*.yaml", "**/*.yaml", "*.yml", "**/*.yml"],
    rules: {
      // https://github.com/ota-meshi/eslint-plugin-toml/issues/234
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
  eslintConfigPrettier, // Best if last
];
