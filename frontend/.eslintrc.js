module.exports = {
  root: true,
  env: {
    node: true,
    es2020: true,
    browser: true,
  },
  extends: [
    "eslint:recommended",
    "plugin:vue/recommended",
    "plugin:vue-scoped-css/recommended",
    "plugin:prettier/recommended",
    "@vue/prettier",
    "adjunct",
  ],
  parserOptions: {
    parser: "babel-eslint",
    ecmaVersion: 2020,
    ecmaFeatures: {
      impliedStrict: true,
    },
    sourceType: "module",
  },
  plugins: ["prettier"],
  rules: {
    "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
    "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off",
    "space-before-function-paren": "off",
    "prettier/prettier": "warn",
    "simple-import-sort/sort": "warn",
  },
  ignorePatterns: ["public", "node_modules", "*~"],
};
