/*
 * The metadata dialog's Reading Lists row: one chip per list the selection
 * is in, naming a single comic's place, each opening its list.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import MetadataReadingListsRow from "@/components/metadata/metadata-reading-lists-row.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

function mountRow(readingLists) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    initialState: { metadata: { md: { readingLists } } },
  });
  const wrapper = mount(
    {
      components: { MetadataReadingListsRow },
      template: "<table><tbody><MetadataReadingListsRow /></tbody></table>",
    },
    { global: { plugins: [pinia, vuetify] } },
  );
  return { wrapper, browser: useBrowserStore() };
}

describe("metadata reading lists row", () => {
  test("names a comic's place in each list", () => {
    const { wrapper } = mountRow([
      { pk: 3, name: "Civil War", position: 12, count: 98 },
      { pk: 4, name: "Marvel 2006", position: null, count: 40 },
    ]);
    const labels = wrapper.findAll(".v-chip").map((chip) => chip.text());
    expect(labels).toEqual(["Civil War · 12 of 98", "Marvel 2006 · 40"]);
  });

  test("a chip opens its list in the reading lists view", async () => {
    const { wrapper, browser } = mountRow([
      { pk: 3, name: "Civil War", position: 1, count: 2 },
    ]);
    await wrapper.find(".v-chip").trigger("click");
    expect(browser.routeWithSettings).toHaveBeenCalledWith(
      { topCollection: "arcs" },
      { name: "browser", params: { collection: "arcs", pks: "3", page: 1 } },
    );
  });

  test("renders nothing without lists", () => {
    const { wrapper } = mountRow([]);
    expect(wrapper.find(".readingListsRow").exists()).toBe(false);
  });
});
