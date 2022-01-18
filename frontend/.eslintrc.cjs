module.exports = {
  root: true,
  env: {
    node: true,
    es2021: true,
    browser: true,
    jest: { globals: true },
  },
  extends: [
    "eslint:recommended",
    "plugin:vue/recommended",
    "plugin:vue-scoped-css/recommended",
    // CODE QUALITY
    "plugin:sonarjs/recommended",
    "plugin:unicorn/all",
    // LANGS
    "plugin:json/recommended",
    "plugin:markdown/recommended",
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
    "@vue/eslint-config-prettier",
    // SECURITY
    "plugin:no-unsanitized/DOM",
    "plugin:security/recommended",
  ],
  parser: "vue-eslint-parser",
  parserOptions: {
    ecmaFeatures: {
      impliedStrict: true,
    },
    ecmaVersion: 2022,
    parser: "@babel/eslint-parser",
    requireConfigFile: false,
    sourceType: "module",
  },
  plugins: [
    "array-func",
    "eslint-comments",
    "jest",
    "jest-async",
    "json",
    "import",
    "markdown",
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
    "vue",
  ],
  rules: {
    "import/no-unresolved": [
      "error",
      {
        ignore: ["^[@]"],
      },
    ],
    "jest-async/expect-return": "error",
    "max-params": ["warn", 4],
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
    "vue/no-deprecated-filter": "off", // Vue 3
    "vue/no-deprecated-v-on-native-modifier": "off", // Vue 3
  },
  ignorePatterns: ["*~", "coverage", "dist", "node_modules", "public"],
};
