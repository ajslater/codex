module.exports = {
  plugins: ["vitest"],
  extends: [
    "../.eslintrc.cjs",
    // TEST LIBRARIES
  ],
  rules: {
    "vitest/lower-case-title": 2,
  },
  env: {
    jest: true, // why not vitest?
  },
};
