module.exports = {
  root: true,
  env: {
    node: true,
    es2021: true,
    browser: true,
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
    ecmaFeatures: {
      impliedStrict: true,
    },
    ecmaVersion: 2022,
  },
  overrides: [
    {
      files: ["*.md"],
      parser: "markdown-eslint-parser",
      rules: {
        "prettier/prettier": ["error", { parser: "markdown" }],
      },
    },
    {
      files: ["*.md.js"], // Will match js code inside *.md files
      rules: {
        // disable 2 core eslint rules 'no-unused-vars' and 'no-undef'
        "no-unused-vars": "off",
        "no-undef": "off",
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
    "import/no-unresolved": [
      "error",
      {
        ignore: ["^[@]"],
      },
    ],
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
    "comics",
    "config",
    "dist",
    "frontend",
    "node_modules",
    "test_results",
    "typings",
  ],
};
