module.exports = {
  root: true,
  extends: [
    "../.eslintrc.cjs",
    // VUE
    "plugin:vue/recommended",
    "plugin:vue-scoped-css/recommended", // XXX breaks eslint_d, vue3- prefix
    "@vue/eslint-config-prettier",
  ],
  parser: "vue-eslint-parser",
  plugins: ["vue"],
  rules: {
    "unicorn/prefer-node-protocol": 0,
    "vue/no-deprecated-filter": "off", // Vue 3
    "vue/no-deprecated-v-on-native-modifier": "off", // Vue 3
  },
  overrides: [
    {
      files: ["*.md"],
      parser: "eslint-plugin-markdownlint/parser",
      extends: ["plugin:markdownlint/recommended"],
      rules: {
        "markdownlint/md013": "warn",
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
