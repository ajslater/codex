/*
 * The metadata pane's reprints row.
 *
 * The backend composes ``Reprint.name`` from whichever of series name,
 * volume, issue and language the reprint carries, so the client just
 * renders it like any other ``{pk, name, url}`` tag row, under the
 * capital-cased key.
 *
 * Chips route through the ``reprints`` browser filter, the key phase E
 * registers.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, test } from "vitest";

import MetadataTags from "@/components/metadata/metadata-tags.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";
import { useMetadataStore } from "@/stores/metadata";

const REPRINTS = Object.freeze([
  { pk: 7, name: "Kapitän Wissenschaft" },
  { pk: 8, name: "Capitan Sciencia v1 (es)" },
]);

describe("metadata store reprints row", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  test("labels the reprints row Reprints", () => {
    const store = useMetadataStore();
    // Copied: the tags getter sorts the row in place.
    store.md = { reprints: [...REPRINTS] };

    const row = store.tags.Reprints;
    expect(row.filter).toBe("reprints");
    expect(row.tags.map((tag) => tag.name)).toStrictEqual([
      "Capitan Sciencia v1 (es)",
      "Kapitän Wissenschaft",
    ]);
  });

  test("omits the row when there are no reprints", () => {
    const store = useMetadataStore();
    store.md = { reprints: [] };

    expect(store.tags["Reprints"]).toBeUndefined();
  });
});

describe("reprint chips", () => {
  function mountTags() {
    const pinia = createTestingPinia({
      initialState: {
        browser: {
          settings: { show: {}, filters: {}, topCollection: "publishers" },
        },
        metadata: { md: { collection: "comics", ids: [1] } },
      },
    });
    const wrapper = mount(MetadataTags, {
      global: { plugins: [pinia, vuetify] },
      props: { label: "", filter: "reprints", values: REPRINTS },
    });
    return { wrapper, browserStore: useBrowserStore() };
  }

  test("renders the composed names", () => {
    const { wrapper } = mountTags();
    const text = wrapper.text();
    expect(text).toContain("Kapitän Wissenschaft");
    expect(text).toContain("Capitan Sciencia v1 (es)");
  });

  test("clicking filters the browser by the reprint pk", async () => {
    const { wrapper, browserStore } = mountTags();

    await wrapper.findAll(".v-chip")[0].trigger("click");

    expect(browserStore.routeWithSettings).toHaveBeenCalledWith(
      { filters: { reprints: [7] } },
      { name: "browser", params: { collection: "root", pks: "0", page: 1 } },
    );
  });
});
