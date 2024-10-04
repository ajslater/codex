import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginVitest from "eslint-plugin-vitest";
import eslintPluginVue from "eslint-plugin-vue";
import eslintPluginVueScopedCSS from "eslint-plugin-vue-scoped-css";
import path from "path";
import { fileURLToPath } from "url";

import baseConfig from "../eslint.config.js";

const FLAT_RECOMMENDED = "flat/recommended";
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default [
  ...baseConfig,
  ...eslintPluginVue.configs[FLAT_RECOMMENDED],
  ...eslintPluginVueScopedCSS.configs[FLAT_RECOMMENDED],
  {
    rules: {
      "no-console": [
        "warn",
        { allow: ["clear", "debug", "info", "warn", "error"] },
      ],
    },
    settings: {
      "import/extensions": [".js", ".vue"],
      "import/resolver": {
        alias: {
          map: [["@", path.resolve(__dirname, "src")]],
        },
      },
    },
  },
  {
    files: ["tests/**"],
    plugins: {
      vitest: eslintPluginVitest,
    },
    rules: {
      ...eslintPluginVitest.configs.recommended.rules,
    },
  },
  eslintConfigPrettier, // Best if last
];
