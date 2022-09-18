module.exports = {
  extends: [
    "../.eslintrc.cjs",
    // VUE
    "plugin:vue/recommended",
    "plugin:vue-scoped-css/recommended", // XXX breaks eslint_d, vue3- prefix
    "prettier", // eslint-prettier-config AFTER vue/recommended
  ],
  parser: "vue-eslint-parser",
  plugins: ["vue"],
  rules: {
    "vue/no-deprecated-filter": "off", // Vue 3
    "vue/no-deprecated-v-on-native-modifier": "off", // Vue 3
  },
  overrides: [
    {
      files: ["*.md"],
      parser: "eslint-plugin-markdownlint/parser",
      extends: ["plugin:markdownlint/recommended"],
      rules: {
        "markdownlint/md013": "off",
        "markdownlint/md033": "off",
      },
    },
  ],
  ignorePatterns: ["!frontend", "coverage", "components.d.ts"],
  settings: {
    "import/resolver": {
      alias: {
        map: [["@", "./src"]],
      },
    },
  },
};
