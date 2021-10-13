/* eslint-disable unicorn/prefer-module */
const { defaults } = require("jest-config");
module.exports = {
  preset: "@vue/cli-plugin-unit-jest",
  moduleFileExtensions: [...defaults.moduleFileExtensions, "vue"],
};
/* eslint-enable unicorn/prefer-module */
