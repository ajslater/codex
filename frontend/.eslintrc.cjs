module.exports = {
  root: true,
  extends: [
    "../.eslintrc.cjs",
    // VUE
    "plugin:vue/recommended",
    "plugin:vue-scoped-css/recommended",
    "@vue/eslint-config-prettier",
  ],
  parser: "vue-eslint-parser",
  parserOptions: {
    parser: "@babel/eslint-parser",
    requireConfigFile: false,
    sourceType: "module",
  },
  plugins: ["vue"],
  rules: {
    "vue/no-deprecated-filter": "off", // Vue 3
    "vue/no-deprecated-v-on-native-modifier": "off", // Vue 3
  },
  ignorePatterns: ["coverage", "public", "package-lock.json"],
};
