module.exports = {
  plugins: ["vitest"],
  extends: [
    "../.eslintrc.cjs",
    // TEST LIBRARIES
  ],
  rules: {
    "vitest/max-nested-describe": [
      "error",
      {
        max: 3,
      },
    ],
    // importing vitest causes all these :(
    "import/named": 0,
    "import/namespace": 0,
    "import/no-duplicates": 0,
    "import/no-unresolved": 0,
  },
};
