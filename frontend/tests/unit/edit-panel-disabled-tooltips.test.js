/*
 * Tests for the tag edit panel's disabled-format tooltips.
 *
 * Behavior locked in here:
 *   - Every control that is disabled because its field is unsupported by the
 *     selected metadata formats is wrapped by an element carrying the
 *     "Not supported by selected metadata formats" title, so hovering the
 *     disabled control explains why it is disabled.
 *   - The Add Universe button is the headline case: disabled + explained when
 *     MetronInfo is off, enabled + unexplained when MetronInfo is on.
 *   - Per-row table inputs (e.g. Universe designation) and the Main
 *     Character / Main Team selects are covered too.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import EditPanel from "@/components/metadata/edit-mode/edit-panel.vue";
import vuetify from "@/plugins/vuetify";

const DISABLED_TIP = "Not supported by selected metadata formats";

async function mountPanel({ formats = ["COMIC_INFO"], md = {} } = {}) {
  const pinia = createTestingPinia({
    initialState: {
      metadata: { md },
      admin: { taggingDefaults: { defaultFormats: formats } },
      browser: { settings: { twentyFourHourTime: false } },
    },
  });
  const wrapper = mount(EditPanel, {
    props: { book: { pk: 1, collection: "comics", ids: [1] } },
    global: { plugins: [pinia, vuetify] },
  });
  // mounted() sets selectedFormats from the defaults and seeds the patch from
  // metadata; both are reactive, so let the DOM flush before asserting.
  await flushPromises();
  return wrapper;
}

function findButton(wrapper, label) {
  return wrapper.findAll("button").find((b) => b.text().includes(label));
}

describe("EditPanel — Add Universe tooltip", () => {
  test("disabled and explained when MetronInfo is not selected", async () => {
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    const btn = findButton(wrapper, "Add Universe");
    expect(btn).toBeTruthy();
    expect(btn.element.disabled).toBe(true);
    expect(btn.element.parentElement.getAttribute("title")).toBe(DISABLED_TIP);
  });

  test("enabled and unexplained when MetronInfo is selected", async () => {
    const wrapper = await mountPanel({ formats: ["METRON_INFO"] });
    const btn = findButton(wrapper, "Add Universe");
    expect(btn.element.disabled).toBe(false);
    expect(btn.element.parentElement.getAttribute("title")).not.toBe(
      DISABLED_TIP,
    );
  });
});

describe("EditPanel — disabled per-row inputs", () => {
  test("a universe row's input carries the tooltip on its cell", async () => {
    const wrapper = await mountPanel({
      formats: ["COMIC_INFO"],
      md: { universes: [{ name: "Earth-616", designation: "Prime" }] },
    });
    const designation = wrapper
      .findAll("input")
      .find((i) => i.element.value === "Prime");
    expect(designation).toBeTruthy();
    expect(designation.element.disabled).toBe(true);
    expect(designation.element.closest("td").getAttribute("title")).toBe(
      DISABLED_TIP,
    );
  });

  test("Add Identifier button is wrapped with the tooltip mechanism", async () => {
    // Identifiers are supported by both formats today, so the wrapper title is
    // empty — but the wrapper element exists so it explains itself if a future
    // format drops identifier support.
    const wrapper = await mountPanel({ formats: ["COMIC_INFO"] });
    const btn = findButton(wrapper, "Add Identifier");
    expect(btn.element.parentElement.hasAttribute("title")).toBe(true);
  });
});

describe("EditPanel — protagonist selects", () => {
  test("Main Character and Main Team explain themselves when protagonist is unsupported", async () => {
    const wrapper = await mountPanel({
      formats: ["METRON_INFO"],
      md: {
        characters: [{ name: "Spider-Man" }],
        teams: [{ name: "Avengers" }],
      },
    });
    const explained = wrapper
      .findAll("div[title]")
      .filter((d) => d.attributes("title") === DISABLED_TIP)
      .map((d) => d.text());
    expect(explained.some((t) => t.includes("Main Character"))).toBe(true);
    expect(explained.some((t) => t.includes("Main Team"))).toBe(true);
  });
});

export default {};
