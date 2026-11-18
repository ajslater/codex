/*
 * The metadata toolbar has no shelf button of its own.
 *
 * It used ``<ShelfMenu>`` and imported it but never registered it, so Vue
 * rendered an unknown ``<shelfmenu>`` element and warned on every open.
 * Shelving from the metadata dialog lives in its Shelves row.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, test, vi } from "vitest";

import MetadataControls from "@/components/metadata/metadata-controls.vue";
import vuetify from "@/plugins/vuetify";
import { useMetadataStore } from "@/stores/metadata";

function mountControls() {
  const pinia = createTestingPinia({
    initialState: { browser: { settings: { search: "" } } },
  });
  useMetadataStore().md = {
    loaded: true,
    collection: "comics",
    ids: [1, 2],
    pageCount: 3,
  };
  return mount(MetadataControls, {
    global: {
      plugins: [pinia, vuetify],
      mocks: { $route: { name: "browser" } },
      stubs: {
        DownloadButton: true,
        MarkReadButton: true,
        OnlineTagLauncherDialog: true,
      },
    },
    props: {
      collection: "comics",
      book: { collection: "comics", ids: [1, 2] },
    },
  });
}

describe("MetadataControls", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("renders no unresolved shelf element", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const wrapper = mountControls();

    expect(wrapper.find("#shelfButton").exists()).toBe(false);
    expect(wrapper.html().toLowerCase()).not.toContain("<shelfmenu");
    const unresolved = warn.mock.calls.filter((args) =>
      String(args[0]).includes("Failed to resolve component"),
    );
    expect(unresolved).toStrictEqual([]);
  });
});
