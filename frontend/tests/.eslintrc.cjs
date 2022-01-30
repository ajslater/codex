module.exports = {
  env: {
    jest: { globals: true },
  },
  plugins: ["jest", "jest-async"],
  extends: [
    "../.eslintrc.cjs",
    // TEST LIBRARIES
    "plugin:jest/all",
  ],
  rules: {
    "jest-async/expect-return": "error",
  },
};
