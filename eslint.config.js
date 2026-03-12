import baseConfig from "./cfg/eslint.config.base.js";

export default [
  {
    name: "codexIgnores",
    ignores: [
      "codex/_vendor/",
      "codex/static_build/",
      "codex/static_root/",
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/**/*.html", // Handled by djlint
      "codex/templates/pwa/serviceworker-register.js", // removes eslint-disable that it then complains about
      "frontend",
    ],
  },
  ...baseConfig,
  {
    files: ["tests/files/comicbox.update.yaml"],
    rules: {
      "yml/no-empty-mapping-value": "off",
    },
  },
];
