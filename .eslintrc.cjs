module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    // CODE QUALITY
    "plugin:sonarjs/recommended",
    "plugin:unicorn/all",
    // LANGS
    "plugin:json/recommended",
    "plugin:markdown/recommended",
    //"plugin:md/recommended",
    "plugin:yaml/recommended",
    // PRACTICES
    "plugin:array-func/recommended",
    "plugin:eslint-comments/recommended",
    "plugin:no-use-extend-native/recommended",
    "plugin:optimize-regex/all",
    "plugin:promise/recommended",
    "plugin:import/recommended",
    "plugin:switch-case/recommended",
    // PRETTIER
    "plugin:prettier/recommended",
    // SECURITY
    "plugin:no-unsanitized/DOM",
    "plugin:security/recommended",
  ],
  parserOptions: {
    sourceType: "module",
    ecmaFeatures: {
      impliedStrict: true,
    },
  },
  overrides: [
    {
      files: ["*.md"],
      parser: "markdown-eslint-parser",
      rules: {
        "prettier/prettier": ["error", { parser: "markdown" }],
      },
    },
  ],
  plugins: [
    "array-func",
    "eslint-comments",
    "json",
    "import",
    "markdown",
    //"md",
    "no-constructor-bind",
    "no-secrets",
    "no-unsanitized",
    "no-use-extend-native",
    "optimize-regex",
    "prettier",
    "promise",
    "simple-import-sort",
    "switch-case",
    "security",
    "sonarjs",
    "unicorn",
    "yaml",
  ],
  rules: {
    "max-params": ["warn", 4],
    /*
     md/remark plugins can't be read by eslint
     https://github.com/standard-things/esm/issues/855
    "md/remark": [ "error",
      {
        plugins: [
          "gfm",
          "preset-lint-consistent",
          "preset-lint-markdown-style-guide",
          "preset-lint-recommended",
          "preset-prettier"
        ],
      }
    ],
    */
    "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
    "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off",
    "no-constructor-bind/no-constructor-bind": "error",
    "no-constructor-bind/no-constructor-state": "error",
    "no-secrets/no-secrets": "error",
    "eslint-comments/no-unused-disable": 1,
    "prettier/prettier": "warn",
    "security/detect-object-injection": "off",
    "simple-import-sort/exports": "warn",
    "simple-import-sort/imports": "warn",
    "space-before-function-paren": "off",
    "switch-case/newline-between-switch-case": "off", // Malfunctioning
    "unicorn/prevent-abbreviations": "off",
    "unicorn/filename-case": [
      "error",
      { case: "kebabCase", ignore: [".*.md"] },
    ],
  },
  ignorePatterns: [
    "*~",
    "**/__pycache__",
    ".git",
    "!.circleci",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "cache/*",
    "!cache/packages",
    "cache/packages/*",
    "!cache/packages/README.md",
    "codex/_vendor/haystack",
    "codex/static_build",
    "codex/static_root",
    "codex/templates/**/*.html",
    "comics",
    "config",
    "dist",
    "package-lock.json",
    "test-results",
    "typings",
  ],
};
