module.exports = {
  extends: [
    // VUE
    "plugin:vue/vue3-recommended",
    "plugin:vue-scoped-css/vue3-recommended", // XXX breaks eslint_d
    "prettier", // eslint-prettier-config AFTER vue/recommended
  ],
  parser: "vue-eslint-parser",
  parserOptions: {
    ecmaVersion: "latest",
    ecmaFeatures: {
      impliedStrict: true,
    },
  },
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
