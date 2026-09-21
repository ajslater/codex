/*
 * The theme and style contract.
 *
 * Deliberately a contract test, not a rendering test: it pins what
 * src/plugins/vuetify.js declares and what the style blocks are allowed
 * to say, so a rename, a stray hex or a typo is caught by name instead
 * of by someone noticing a colour looks wrong.
 *
 *   - The single dark codex theme, and every colour it declares.
 *   - Component defaults pass theme tokens, never resolved hex — a hex
 *     lands as an inline style and stops following the theme.
 *   - No `rbg(` typos: an invalid function voids the whole declaration
 *     silently, which is how a card hover border went years unrendered.
 */
import { describe, expect, test } from "vitest";

import vuetify from "@/plugins/vuetify";

const WHITE = "#FFFFFF";
const DISABLED = "#808080";

describe("theme contract", () => {
  // `themes.value` holds the raw declared definition; `computedThemes`
  // would include Vuetify's merged dark defaults. The contract is what
  // Codex declares.
  const theme = vuetify.theme.themes.value.codexTheme;

  test("is the dark codex theme, and it is the one in use", () => {
    // Vuetify always carries its own `light` and `dark` alongside the
    // declared theme; what matters is which one is selected.
    expect(vuetify.theme.name.value).toBe("codexTheme");
    expect(theme.dark).toBe(true);
  });

  test("declares exactly these colours", () => {
    expect(theme.colors).toEqual({
      primary: "#CC7B19",
      "on-primary": "#000000",
      "primary-darken-1": "#965B13",
      error: "#DC143C",
      success: "#14dc3c",
      warning: "#E6BD0D",
      "surface-light": "#2A2A2A",
      "link-hover": WHITE,
      "text-primary": WHITE,
      "text-header": "#D3D3D3",
      "text-secondary": "#A9A9A9",
      "text-disabled": DISABLED,
      "icons-inactive": DISABLED,
      "include-group": "#141",
      "exclude-group": "#411",
    });
  });

  test("component defaults pass theme tokens, never hex", () => {
    // A resolved hex lands as an inline style on the element and stops
    // following the theme; a token resolves to a class at render time.
    const hexed = Object.entries(vuetify.defaults.value)
      .filter(([, props]) => /^#/.test(props?.color ?? ""))
      .map(([name]) => name);
    expect(hexed).toEqual([]);
  });
});

// Vite's own loader, the way tests/unit/rules-plugin.test.js scans source.
const SOURCES = Object.entries(
  import.meta.glob(["@/**/*.vue", "@/**/*.scss"], {
    query: "?raw",
    import: "default",
    eager: true,
  }),
);

const filesMatching = (pattern) =>
  SOURCES.filter(([, source]) => pattern.test(source)).map(([file]) => file);

describe("style contract", () => {
  test("the source scan found files to scan", () => {
    // A silently empty list would make every test below vacuous.
    expect(SOURCES.length).toBeGreaterThan(100);
  });

  test("no rbg( typos", () => {
    expect(filesMatching(/\brbg\(/)).toEqual([]);
  });

  test("theme variables are kebab-case", () => {
    // The eight custom tokens were camelCase until the rename; a
    // reintroduced one resolves to nothing and the declaration is
    // dropped without a word.
    expect(filesMatching(/--v-theme-[a-z]+[A-Z]/)).toEqual([]);
  });
});

export default {};
