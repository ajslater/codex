/*
 * The metadata dialog's tags table, whose first row is the Shelves row.
 *
 * Behavior locked in here:
 *   - An untagged comic shows an anonymous visitor no tags table at all:
 *     the Shelves row is theirs to never see, so the table would be empty.
 *   - A signed-in user still gets the table, for the Shelves row alone.
 *   - Everyone sees the Reading Lists row: a list is shown to whoever may
 *     see it, signed in or not.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import MetadataBody from "@/components/metadata/metadata-body.vue";
import MetadataTagsTable from "@/components/metadata/tags-table.vue";
import vuetify from "@/plugins/vuetify";

const BOOK = Object.freeze({ collection: "comics", ids: [5], pk: 5 });

function mountBody(user, readingLists = []) {
  const pinia = createTestingPinia({
    initialState: {
      auth: { user },
      browser: {
        settings: { filters: {}, show: {}, topCollection: "publishers" },
      },
      metadata: { md: { collection: "comics", ids: [5], pk: 5, readingLists } },
      shelves: { shelves: [] },
    },
  });
  return mount(MetadataBody, {
    props: { book: BOOK },
    global: {
      plugins: [pinia, vuetify],
      // The text and ratings sections link through the router; not tested.
      stubs: { MetadataRatings: true, MetadataText: true },
    },
  });
}

// The tags table is the one with the Shelves row slot; credits come first.
const tagsTable = (wrapper) => wrapper.findAllComponents(MetadataTagsTable)[1];

describe("metadata tags table", () => {
  test("an untagged comic shows an anonymous visitor no table", () => {
    const wrapper = mountBody();
    expect(tagsTable(wrapper).find("table").exists()).toBe(false);
  });

  test("a signed-in user gets the table for the Shelves row", () => {
    const wrapper = mountBody({ id: 1, username: "alice" });
    const table = tagsTable(wrapper);
    expect(table.find("table").exists()).toBe(true);
    expect(table.find("td.key").text()).toBe("Shelves");
  });

  test("an anonymous visitor sees the reading lists that hold a comic", () => {
    const lists = [{ pk: 3, name: "Civil War", position: 2, count: 7 }];
    const table = tagsTable(mountBody(undefined, lists));
    expect(table.find("tr.readingListsRow").exists()).toBe(true);
    expect(table.find("td.key").text()).toBe("Reading Lists");
  });
});
