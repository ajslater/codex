/*
 * Tests for ``browser-toolbar-title.vue`` — the centred collection title.
 *
 * A series title carries the series' year range, and every collection
 * page but the root listing gets a Tags button that opens the browsed
 * collection's own metadata, built like a browser card's book.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import BrowserToolbarTitle from "@/components/browser/toolbars/browser-toolbar-title.vue";
import MetadataDialog from "@/components/metadata/metadata-dialog.vue";
import vuetify from "@/plugins/vuetify";

function mountTitle({ params, title = {}, modelCollection = "comics" }) {
  const pinia = createTestingPinia({
    initialState: {
      browser: { page: { title, modelCollection } },
    },
  });
  return mount(BrowserToolbarTitle, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { params } },
      stubs: { MetadataDialog: true },
    },
  });
}

const titleText = (wrapper) => wrapper.find("#browserTitle").text();

describe("BrowserToolbarTitle — title", () => {
  test("names the root listing All", () => {
    const wrapper = mountTitle({
      params: { collection: "publishers" },
      title: { collectionName: "Publishers", collectionCount: 0 },
      modelCollection: "publishers",
    });
    expect(titleText(wrapper)).toBe("All");
  });

  test("follows a series name with its years", () => {
    const wrapper = mountTitle({
      params: { collection: "series", parentIds: "5" },
      title: {
        collectionName: "Amazing Spider-Man",
        collectionCount: 0,
        collectionStartYear: 1963,
        collectionEndYear: 1996,
      },
    });
    expect(titleText(wrapper)).toBe("Amazing Spider-Man 1963–1996");
  });

  test("shows a series without years by name alone", () => {
    const wrapper = mountTitle({
      params: { collection: "series", parentIds: "5" },
      title: {
        collectionName: "Amazing Spider-Man",
        collectionCount: 0,
        collectionStartYear: null,
        collectionEndYear: null,
      },
    });
    expect(titleText(wrapper)).toBe("Amazing Spider-Man");
  });

  test("keeps a volume's own name and count", () => {
    const wrapper = mountTitle({
      params: { collection: "volumes", parentIds: "7" },
      title: {
        collectionName: "1963",
        collectionNumberTo: null,
        collectionCount: 3,
        collectionStartYear: null,
        collectionEndYear: null,
      },
    });
    expect(titleText(wrapper)).toBe("(1963) of 3");
  });
});

describe("BrowserToolbarTitle — Tags button", () => {
  test("is absent on the root listing", () => {
    const wrapper = mountTitle({
      params: { collection: "publishers" },
      title: { collectionName: "Publishers", collectionCount: 0 },
      modelCollection: "publishers",
    });
    expect(wrapper.findComponent(MetadataDialog).exists()).toBe(false);
  });

  test("opens the browsed series' own metadata", () => {
    const wrapper = mountTitle({
      params: { collection: "series", parentIds: "5" },
      title: { collectionName: "Amazing Spider-Man", collectionCount: 0 },
    });
    const dialog = wrapper.findComponent(MetadataDialog);
    expect(dialog.exists()).toBe(true);
    expect(dialog.props("book")).toStrictEqual({
      collection: "series",
      ids: [5],
      pk: 5,
      childCount: 0,
    });
    expect(dialog.props("toolbar")).toBe(true);
    expect(dialog.props("size")).toBe("small");
    expect(dialog.props("density")).toBe("compact");
  });
});
