import eslintJson from "@eslint/json";

export default [
  {
    ignores: [
      "!.circleci",
      "**/__pycache__/",
      "*~",
      ".git/",
      ".mypy_cache/",
      ".pytest_cache/",
      ".ruff_cache/",
      ".venv/",
      "codex/_vendor/",
      "codex/static_build/",
      "codex/static_root/",
      "codex/templates/*.html", // Handled by djlint
      "codex/templates/**/*.html", // Handled by djlint
      "comics/",
      "config/",
      "dist/",
      "**/node_modules/",
      "**/package-lock.json",
      "test-results/",
      "typings/",
      "**/*.js",
      "**/*.vue",
      "**/*.scss",
      "**/*.css",
    ],
  },
  {
    files: ["*.json", "**/*.json"],
    ...eslintJson.configs.recommended,
    language: "json/json",
  },
  {
    files: ["frontend/src/choices/browser-map.json"],
    rules: {
      "json/no-empty-keys": "off",
    },
  },
];
