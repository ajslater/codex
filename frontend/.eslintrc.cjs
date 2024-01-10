require("@rushstack/eslint-patch/modern-module-resolution"); // for @vue/esl-c-prettier

module.exports = {
  extends: [
    // VUE
    "plugin:vue/vue3-recommended",
    "plugin:vue-scoped-css/vue3-recommended",
    //"prettier", // eslint-config-prettier AFTER vue/recommended
    "@vue/eslint-config-prettier", // Must come at the end.
  ],
  parser: "vue-eslint-parser",
  parserOptions: {
    ecmaVersion: "latest",
    ecmaFeatures: {
      impliedStrict: true,
    },
  },
  overrides: [
    {
      files: ["tests/**"],
      plugins: ["vitest"],
      extends: ["plugin:vitest/recommended"],
    },
  ],
  plugins: ["vue"],
  ignorePatterns: [
    "coverage",
    "components.d.ts",
    "!frontend",
    "node_modules",
    "*.md",
  ],
  settings: {
    "import/resolver": {
      alias: {
        map: [["@", "./src"]],
      },
    },
  },
};
