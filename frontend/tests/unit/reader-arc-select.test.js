/*
 * Tests for the reader's reading-order picker.
 *
 * Behavior locked in here:
 *   - An alternate-series arc ("reprints") renders with its own subtitle.
 *     Subtitles otherwise come from the browse TOP_COLLECTION labels, which
 *     have no "reprints" key — singularizing that undefined used to throw.
 *   - Browse-collection arcs keep their singularized subtitles.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import ReaderArcSelect from "@/components/reader/toolbars/top/reader-arc-select.vue";
import vuetify from "@/plugins/vuetify";

function mountArcSelect(arcs, arc = { collection: "series", ids: "1" }) {
  const pinia = createTestingPinia({
    initialState: { reader: { arcs, arc } },
  });
  return mount(ReaderArcSelect, {
    global: { plugins: [pinia, vuetify] },
  });
}

describe("reader arc select", () => {
  test("a reprint arc gets its own subtitle and icon", () => {
    const wrapper = mountArcSelect({
      series: { 1: { name: "Ser" } },
      reprints: { "2,3": { name: "Crossover" } },
    });
    const items = wrapper.vm.items;
    const reprint = items.find((item) => item.collection === "reprints");
    expect(reprint).toBeTruthy();
    expect(reprint.subtitle).toBe("Reprints");
    expect(reprint.title).toBe("Crossover");
    expect(reprint.prependIcon).toBeTruthy();
  });

  test("browse collections keep their singularized subtitles", () => {
    const wrapper = mountArcSelect({
      series: { 1: { name: "Ser" } },
      arcs: { 5: { name: "The Big One" } },
      reprints: { "2,3": { name: "Crossover" } },
    });
    const byCollection = Object.fromEntries(
      wrapper.vm.items.map((item) => [item.collection, item.subtitle]),
    );
    expect(byCollection.series).toBe("Series");
    expect(byCollection.arcs).toBe("Story Arc");
    expect(byCollection.reprints).toBe("Reprints");
  });
});
