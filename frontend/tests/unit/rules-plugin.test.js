/*
 * Guards the composite Vuetify + rules-plugin export in src/plugins/vuetify.js.
 *
 *   - Codex's custom aliases ($intRange, $numRange, $notIn) resolve through a
 *     plain mount with the shared plugin, with byte-identical messages.
 *   - An alias array that does not resolve is NOT an error: Vuetify warns and
 *     skips it, so the field validates with no rules at all. That silent
 *     fail-open happens both without the plugin and with a misspelled alias
 *     name, which is why the plugin rides inside the default export and why
 *     every $alias used under src/ is checked against the registry here.
 */
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { createVuetify } from "vuetify";
import { VTextField } from "vuetify/components";
import { aliases, mdi } from "vuetify/iconsets/mdi-svg";

import { createCodexRulesPlugin } from "@/plugins/rules";
import vuetify from "@/plugins/vuetify";

const mountField = (rules, modelValue, plugin = vuetify) =>
  mount(VTextField, {
    props: { rules, modelValue },
    global: { plugins: [plugin] },
  });

const errorsFor = (rules, value, plugin) =>
  mountField(rules, value, plugin).vm.validate();

let warn;
beforeEach(() => {
  warn = vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
  warn.mockRestore();
});

describe("rules plugin", () => {
  test("$intRange rejects out-of-range and non-integers, passes blank", async () => {
    const rules = [["$intRange", [0, 100]]];
    expect(await errorsFor(rules, 101)).toEqual(["Must be 0–100"]);
    expect(await errorsFor(rules, 12.5)).toEqual(["Must be 0–100"]);
    expect(await errorsFor(rules, 100)).toEqual([]);
    for (const blank of [null, "", undefined]) {
      expect(await errorsFor(rules, blank)).toEqual([]);
    }
    expect(warn).not.toHaveBeenCalled();
  });

  test("$intRange substitutes {0}/{1} into a custom message", async () => {
    const rules = [
      ["$intRange", [1, 65_535], "Port must be between {0} and {1}"],
    ];
    expect(await errorsFor(rules, 0)).toEqual([
      "Port must be between 1 and 65535",
    ]);
  });

  test("$numRange accepts decimals inside the range", async () => {
    const rules = [["$numRange", [0, 5], "Must be 0.0–5.0"]];
    expect(await errorsFor(rules, 4.5)).toEqual([]);
    expect(await errorsFor(rules, 5.1)).toEqual(["Must be 0.0–5.0"]);
    expect(warn).not.toHaveBeenCalled();
  });

  test("$notIn reads a getter at validation time", async () => {
    const taken = new Set(["alice"]);
    const field = mountField(
      [["$notIn", () => taken, "Username already used"]],
      "bob",
    );
    expect(await field.vm.validate()).toEqual([]);
    taken.add("bob");
    expect(await field.vm.validate()).toEqual(["Username already used"]);
    expect(warn).not.toHaveBeenCalled();
  });

  test("$notIn passes when the set is unavailable", async () => {
    // useAdminStore.nameSet() returns false when the caller isn't an admin.
    expect(await errorsFor([["$notIn", () => false, "x"]], "bob")).toEqual([]);
  });

  test("REGRESSION GUARD: without the plugin an alias array fails OPEN", async () => {
    const bare = createVuetify({
      icons: { defaultSet: "mdi", aliases, sets: { mdi } },
    });
    expect(await errorsFor([["$intRange", [0, 100]]], 101, bare)).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });

  test("REGRESSION GUARD: a misspelled alias fails OPEN even with the plugin", async () => {
    expect(await errorsFor([["$intRnge", [0, 100]]], 101)).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });

  test("every $alias used under src/components is registered", () => {
    let registry;
    createCodexRulesPlugin(vuetify.locale).install({
      provide: (_key, value) => {
        registry = value;
      },
    });
    const names = Object.keys(registry.aliases);
    const sources = import.meta.glob("@/components/**/*.vue", {
      query: "?raw",
      import: "default",
      eager: true,
    });
    for (const [file, source] of Object.entries(sources)) {
      for (const [, name] of source.matchAll(/\[\s*"\$(\w+)"/g)) {
        expect(names, `${file} uses $${name}`).toContain(name);
      }
    }
  });
});

export default {};
