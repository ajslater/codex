/*
 * Tests for the metadata dialog's Shelves row.
 *
 * Behavior locked in here:
 *   - The row lists the selection's shared shelves (server pks, store
 *     names) as tag chips after the shelf menu, which targets the dialog's
 *     own selection.
 *   - A chip browses its shelf, like any tag chip filters by its tag, and
 *     is highlighted while that shelf filter is on.
 *   - Signed in with no shared shelves, the menu shows alone so the
 *     selection can go on a first shelf; anonymous sessions get no row.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import MetadataShelvesRow from "@/components/metadata/metadata-shelves-row.vue";
import ShelfMenu from "@/components/shelf-menu.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";

const SHELVES = [
  { pk: 1, name: "Favorites", items: {} },
  { pk: 2, name: "Want to Read", items: {} },
  { pk: 3, name: "Unused", items: {} },
];

function mountRow({
  user = { pk: 1 },
  mdShelves = [],
  filterShelves = [],
  book = { collection: "series", ids: [7, 8], pk: 7 },
} = {}) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user },
      browser: {
        settings: {
          filters: { shelves: filterShelves },
          show: {},
          topCollection: "publishers",
        },
      },
      metadata: {
        md: { collection: "series", ids: [7, 8], shelves: mdShelves },
      },
      shelves: { shelves: SHELVES },
    },
  });
  const wrapper = mount(MetadataShelvesRow, {
    props: { book },
    global: { plugins: [pinia, vuetify] },
  });
  return { wrapper, browserStore: useBrowserStore(pinia) };
}

describe("metadata shelves row", () => {
  test("lists the shared shelves after a menu for the selection", () => {
    const { wrapper } = mountRow({ mdShelves: [2, 1, 99] });
    expect(wrapper.find("td.key").text()).toBe("Shelves");
    expect(wrapper.findComponent(ShelfMenu).props()).toMatchObject({
      collection: "series",
      pks: [7, 8],
    });
    const chips = wrapper.findAll(".v-chip").map((chip) => chip.text());
    expect(chips).toEqual(["Favorites", "Want to Read"]);
  });

  test("a chip browses its shelf", async () => {
    const { wrapper, browserStore } = mountRow({ mdShelves: [1] });
    await wrapper.find(".v-chip").trigger("click");
    expect(browserStore.routeWithSettings).toHaveBeenCalledExactlyOnceWith(
      { filters: { shelves: [1] } },
      { name: "browser", params: { collection: "root", pks: "0", page: 1 } },
    );
  });

  test("a chip is highlighted while its shelf filter is on", () => {
    const { wrapper } = mountRow({ mdShelves: [1, 2], filterShelves: [2] });
    const [favorites, wantToRead] = wrapper.findAll(".v-chip");
    expect(favorites.classes()).toContain("v-chip--variant-tonal");
    expect(wantToRead.classes()).toContain("v-chip--variant-flat");
  });

  test("a single row targets its own pk", () => {
    const { wrapper } = mountRow({ book: { collection: "comics", pk: 42 } });
    expect(wrapper.findComponent(ShelfMenu).props()).toMatchObject({
      collection: "comics",
      pks: [42],
    });
  });

  test("no shared shelves leaves the menu alone", () => {
    const { wrapper } = mountRow();
    expect(wrapper.findComponent(ShelfMenu).exists()).toBe(true);
    expect(wrapper.findAll(".v-chip")).toHaveLength(0);
  });

  test("anonymous sessions get no row", () => {
    const { wrapper } = mountRow({ user: null, mdShelves: [1] });
    expect(wrapper.find("tr").exists()).toBe(false);
  });
});
