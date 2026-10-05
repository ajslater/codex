import eslintPluginComments from "@eslint-community/eslint-plugin-eslint-comments/configs";
import eslintJs from "@eslint/js";
import eslintJson from "@eslint/json";
import markdown from "@eslint/markdown";
import eslintPluginStylistic from "@stylistic/eslint-plugin";
import eslintConfigPrettier from "eslint-config-prettier";
import eslintPluginCompat from "eslint-plugin-compat";
import eslintPluginDeMorgan from "eslint-plugin-de-morgan";
import eslintPluginDepend from "eslint-plugin-depend";
import eslintPluginHtml from "eslint-plugin-html";
import eslintPluginImport from "eslint-plugin-import-x";
import eslintPluginMath from "eslint-plugin-math";
import eslintPluginNoSecrets from "eslint-plugin-no-secrets";
import eslintPluginNoUnsanitized from "eslint-plugin-no-unsanitized";
import eslintPluginNoUseExtendNative from "eslint-plugin-no-use-extend-native";
import eslintPluginPackageJson from "eslint-plugin-package-json";
import eslintPluginPerfectionist from "eslint-plugin-perfectionist";
import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import eslintPluginPromise from "eslint-plugin-promise";
import eslintPluginRegexp from "eslint-plugin-regexp";
import eslintPluginSecurity from "eslint-plugin-security";
import eslintPluginSonarjs from "eslint-plugin-sonarjs";
import eslintPluginToml from "eslint-plugin-toml";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import eslintPluginYml from "eslint-plugin-yml";
import { defineConfig } from "eslint/config";
import globals from "globals";

export const FLAT_RECOMMENDED = "flat/recommended";

export const SHARED_RULES = {
  "@stylistic/multiline-comment-style": "off",
  "max-params": ["warn", 4],
  "no-console": "warn",
  "no-debugger": "warn",
  "no-secrets/no-secrets": "error",
  "security/detect-object-injection": "off",
  // Duplicates core no-unused-vars, which has the options worth configuring.
  "sonarjs/no-unused-vars": "off",
  // Unicorn's twin of @stylistic/multiline-comment-style. Both of its autofix
  // modes mangle one-line `/** x */` or starred multi-line block comments.
  "unicorn/single-line-block-comment-style": "off",
};

// Presets for JavaScript. Each becomes its own flat-config entry through
// defineConfig's `extends`, so every preset's rules, plugins and
// languageOptions survive. Spreading them into one object made the last spread
// win and silently discarded everything but SHARED_RULES. `extends` also throws
// on an undefined entry, so a preset name that does not exist fails loudly.
export const JS_PRESETS = Object.freeze([
  eslintJs.configs.recommended,
  eslintPluginComments.recommended,
  eslintPluginCompat.configs[FLAT_RECOMMENDED],
  eslintPluginDeMorgan.configs.recommended,
  eslintPluginDepend.configs[FLAT_RECOMMENDED],
  eslintPluginImport.flatConfigs.recommended, // no `all` preset exists
  eslintPluginMath.configs.recommended,
  eslintPluginNoUnsanitized.configs.recommended,
  eslintPluginPerfectionist.configs["recommended-natural"],
  eslintPluginPromise.configs[FLAT_RECOMMENDED], // no `flat/all` preset exists
  eslintPluginRegexp.configs.all,
  eslintPluginSonarjs.configs.recommended, // no `all` preset exists
  eslintPluginUnicorn.configs.recommended, // `all` adds the opinionated tail
]);

export const CONFIGS = Object.freeze({
  js: {
    extends: JS_PRESETS,
    languageOptions: {
      ecmaVersion: "latest",
    },
    name: "devenv/js",
    rules: {
      ...SHARED_RULES,
    },
  },
});

// @eslint/markdown's processor replaces a Markdown file with its fenced code
// blocks, so with the processor alone the markdown/* rules never see the
// file (docs/processors/markdown.md suggests two ESLint runs instead).
// Returning the whole file as the first block makes ESLint lint the file
// itself, with this config, and then the blocks. ESLint lints a bare-string
// block as the parent file on purpose ("Keep the legacy behavior" in
// lib/linter/linter.js); eslint-plugin-mdx and antfu/eslint-config rely on
// the same mechanism.
const codeBlocks = markdown.processors.markdown;
export const markdownAndCodeBlocks = {
  meta: { name: "devenv/markdown-and-code-blocks", version: "1.0.0" },
  postprocess: ([fileMessages, ...blockMessages], filename) => [
    ...fileMessages,
    ...codeBlocks.postprocess(blockMessages, filename),
  ],
  preprocess: (text, filename) => [
    text,
    ...codeBlocks.preprocess(text, filename),
  ],
  supportsAutofix: true,
};

export const MARKDOWN_CONFIGS = [
  {
    extends: ["markdown/recommended"],
    files: ["**/*.md"],
    // GitHub-Flavored Markdown: tables, autolinks, task lists. Also required
    // by no-bare-urls and table-column-count, which are GFM-only in 9.0.
    // Known upstream crash (eslint/markdown#619, #710): "Custom getLoc()
    // method must be implemented in the subclass", with no file name, means
    // some Markdown file has `<www.…>` or a URL, www host or email inside
    // brackets that are not a link, such as `[https://…]`. --fix also hits it
    // on a bare www host, which no-bare-urls rewrites to `<www.…>`. Write a
    // full link or `<https://…>` instead.
    language: "markdown/gfm",
    languageOptions: { frontmatter: "yaml" },
    // The whole-file pass sees `<!-- eslint-disable-next-line ... -->`
    // comments meant for the code block that follows and would report them
    // unused; --fix would then delete them.
    linterOptions: { reportUnusedDisableDirectives: "off" },
    name: "devenv/markdown",
    plugins: { markdown },
    processor: markdownAndCodeBlocks,
    rules: {
      // remark-preset-lint-markdown-style-guide enforced both of these.
      "markdown/no-bare-urls": "error",
      "markdown/no-duplicate-headings": "error",
    },
  },
  {
    // Fenced js blocks become virtual files such as README.md/1_0.js. Doc
    // snippets are fragments, so relax what @eslint/markdown's processor
    // preset relaxes, plus no-console.
    files: ["**/*.md/*.js"],
    languageOptions: {
      parserOptions: { ecmaFeatures: { impliedStrict: true } },
    },
    name: "devenv/markdown-code-blocks",
    rules: {
      "eol-last": "off",
      "no-console": "off",
      "no-undef": "off",
      "no-unused-expressions": "off",
      "no-unused-vars": "off",
      "padded-blocks": "off",
      strict: "off",
      "unicode-bom": "off",
    },
  },
];

// unicorn/no-top-level-side-effects reports `export default <call>`.
const baseConfig = defineConfig([
  {
    ignores: [
      "**/*.min.css",
      "**/*.min.js",
      "**/__pycache__/",
      "**/coverage/",
      "**/htmlcov/",
      "**/node_modules/",
      "*~",
      ".claude",
      ".eslintcache",
      ".git/",
      ".*cache/",
      ".venv/",
      "bun.lock",
      "dist/",
      "tasks/",
      "test-results/",
      "typings/",
      "uv.lock",
    ],
    name: "globalIgnores",
  },
  eslintPluginNoUseExtendNative.configs.recommended,
  eslintPluginSecurity.configs.recommended,
  eslintPluginStylistic.configs.all,
  eslintPluginPrettierRecommended,
  {
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    plugins: {
      "no-secrets": eslintPluginNoSecrets,
    },
    rules: {
      "prettier/prettier": "warn",
    },
  },
  {
    files: ["**/*.html"],
    plugins: { html: eslintPluginHtml },
  },
  {
    files: ["**/*.js"],
    ...CONFIGS.js,
  },
  {
    files: ["**/eslint.config*.js"],
    name: "devenv/eslint-config-files",
    rules: {
      // Plugin modules export `configs` both as a property of the default
      // export and by name; reading it off the default export is their
      // documented usage.
      "import-x/no-named-as-default-member": "off",
    },
  },
  {
    files: ["**/*.json"],
    plugins: {
      json: eslintJson,
    },
    ...eslintJson.configs.recommended,
    language: "json/json",
  },
  eslintPluginPackageJson.configs.recommended,
  eslintPluginPackageJson.configs.stylistic,
  eslintPluginPackageJson.configs["recommended-publishable"],
  {
    files: ["package.json"],
    languageOptions: {
      parser: "jsonc-eslint-parser",
    },
    plugins: { depend: eslintPluginDepend },
    rules: {
      "depend/ban-dependencies": "error",
    },
  },
  ...MARKDOWN_CONFIGS,
  ...eslintPluginToml.configs.recommended,
  {
    files: ["**/*.toml"],
    rules: {
      "prettier/prettier": ["error", { parser: "toml" }],
    },
  },
  ...eslintPluginYml.configs.standard,
  ...eslintPluginYml.configs.prettier,
  {
    files: ["**/*.yaml", "**/*.yml"],
    rules: {
      "prettier/prettier": ["error", { parser: "yaml" }],
    },
  },
  {
    files: ["**/certbot.yaml", "**/compose*.yaml", "**/.*_treestamps.yaml"],
    rules: {
      "yml/no-empty-mapping-value": "off",
    },
  },
  eslintConfigPrettier, // Best if last
]);

export default baseConfig;
