/*
 * The metadata dialog's Reading Lists row: one chip per list the selection
 * is in, naming a single comic's place, each opening its list. A signed-in
 * user gets the list menu for the selection first, lists or none; the
 * shelves row it replaced did the same.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import MetadataReadingListsRow from "@/components/metadata/metadata-reading-lists-row.vue";
import ReadingListMenu from "@/components/reading-list-menu.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const SELECTION = Object.freeze({ collection: "series", ids: [1, 2] });

function mountRow(readingLists, { user = null, book = SELECTION } = {}) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    initialState: {
      auth: { user },
      metadata: { md: { readingLists } },
      readingLists: { myLists: [], myListsLoaded: true },
    },
  });
  const wrapper = mount(
    {
      components: { MetadataReadingListsRow },
      data: () => ({ book }),
      template:
        '<table><tbody><MetadataReadingListsRow :book="book" /></tbody></table>',
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

  test("a signed-in user gets the list menu for the selection", () => {
    const { wrapper } = mountRow(
      [{ pk: 3, name: "Civil War", position: null, count: 2 }],
      { user: { pk: 1 } },
    );
    const menu = wrapper.findComponent(ReadingListMenu);
    expect(menu.props()).toMatchObject({ collection: "series", pks: [1, 2] });
  });

  test("a single row targets its own pk", () => {
    const { wrapper } = mountRow([], {
      user: { pk: 1 },
      book: { collection: "comics", pk: 42 },
    });
    const menu = wrapper.findComponent(ReadingListMenu);
    expect(menu.props()).toMatchObject({ collection: "comics", pks: [42] });
  });

  test("a signed-in user gets the row in no list, for the menu", () => {
    const { wrapper } = mountRow([], { user: { pk: 1 } });
    expect(wrapper.find(".readingListsRow").exists()).toBe(true);
    expect(wrapper.findAll(".v-chip")).toHaveLength(0);
  });

  test("an anonymous viewer sees the chips and no menu", () => {
    const { wrapper } = mountRow([
      { pk: 3, name: "Civil War", position: 1, count: 2 },
    ]);
    expect(wrapper.findAll(".v-chip")).toHaveLength(1);
    expect(wrapper.findComponent(ReadingListMenu).exists()).toBe(false);
  });
});
