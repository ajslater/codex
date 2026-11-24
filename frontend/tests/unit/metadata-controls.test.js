/*
 * The metadata toolbar has no list button of its own.
 *
 * It once used a menu component it imported but never registered, so Vue
 * rendered an unknown element and warned on every open. Adding to a list
 * from the metadata dialog lives in its Reading Lists row.
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

  test("renders no unresolved component", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

    const wrapper = mountControls();

    expect(wrapper.html().toLowerCase()).not.toContain("<readinglistmenu");
    const unresolved = warn.mock.calls.filter((args) =>
      String(args[0]).includes("Failed to resolve component"),
    );
    expect(unresolved).toStrictEqual([]);
  });
});
