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
  parserOptions: {
    parser: "@babel/eslint-parser",
    requireConfigFile: false,
    sourceType: "module",
    ecmaVersion: 2022,
  },
  plugins: ["vue"],
  rules: {
    "unicorn/prefer-node-protocol": 0,
    "vue/no-deprecated-filter": "off", // Vue 3
    "vue/no-deprecated-v-on-native-modifier": "off", // Vue 3
  },
  ignorePatterns: ["!frontend", "coverage", "components.d.ts"],
  settings: {
    "import/resolver": {
      alias: {
        map: [["@", "./src"]],
      },
    },
  },
};
