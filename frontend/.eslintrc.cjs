module.exports = {
  extends: [
    // VUE
    "plugin:vue/recommended",
    "plugin:vue-scoped-css/recommended", // XXX breaks eslint_d, vue3- prefix
    "prettier", // eslint-prettier-config AFTER vue/recommended
  ],
  /*
  overrides: [
    {
      files: ["*.md"],
      rules: {
        "prettier-vue/prettier": ["warn", { parser: "markdown" }],
      },
    },
  ],
  */
  parser: "vue-eslint-parser",
  parserOptions: {
    ecmaVersion: "latest",
    ecmaFeatures: {
      impliedStrict: true,
    },
  },
  plugins: ["vue"],
  rules: {
    "vue/no-deprecated-filter": "off", // Vue 3
    "vue/no-deprecated-v-on-native-modifier": "off", // Vue 3
  },
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
