/*
 * Regression test for the multi-select metadata toolbar.
 *
 * The action toolbar (MetadataControls — Download / Mark Read / Edit Tags
 * / Tag Online / favorite) used to be gated by
 * `v-if="!multiSelect && !editing"`, so it vanished whenever the dialog
 * was opened from a multi-select. The gate is now `v-if="!editing"`: the
 * toolbar renders for single AND multi-select, and only hides while the
 * edit panel is open. Child components are stubbed so this isolates the
 * gate rather than the whole header tree.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import MetadataControls from "@/components/metadata/metadata-controls.vue";
import MetadataHeader from "@/components/metadata/metadata-header.vue";
import vuetify from "@/plugins/vuetify";
import { useMetadataStore } from "@/stores/metadata";

function mountHeader({ multiSelect = false, editing = false, md = {} } = {}) {
  const pinia = createTestingPinia({
    initialState: { browser: { settings: { search: "" } } },
  });
  const metadataStore = useMetadataStore();
  metadataStore.md = {
    loaded: true,
    collection: "comics",
    ids: [1, 2, 3],
    pageCount: 3,
    ...md,
  };
  return mount(MetadataHeader, {
    global: {
      plugins: [pinia, vuetify],
      stubs: {
        MetadataControls: true,
        MetadataBookCover: true,
        MetadataTags: true,
        MetadataText: true,
      },
    },
    props: {
      collection: "comics",
      book: { collection: "comics", ids: [1, 2, 3] },
      multiSelect,
      editing,
    },
  });
}

describe("MetadataHeader — controls toolbar gate", () => {
  test("shows the toolbar for a single-target view", () => {
    const wrapper = mountHeader({ multiSelect: false });
    expect(wrapper.findComponent(MetadataControls).exists()).toBe(true);
  });

  test("shows the toolbar in multi-select (the regression)", () => {
    const wrapper = mountHeader({ multiSelect: true });
    expect(wrapper.findComponent(MetadataControls).exists()).toBe(true);
  });

  test("hides the toolbar while the edit panel is open", () => {
    const wrapper = mountHeader({ multiSelect: true, editing: true });
    expect(wrapper.findComponent(MetadataControls).exists()).toBe(false);
  });
});

const seriesYears = (md) => mountHeader({ md }).vm.seriesYears;

describe("MetadataHeader — series years", () => {
  test("shows a closed range", () => {
    expect(seriesYears({ seriesStartYear: 1963, seriesEndYear: 1996 })).toBe(
      "(1963–1996)",
    );
  });

  test("leaves an ongoing range open", () => {
    expect(seriesYears({ seriesStartYear: 1963 })).toBe("(1963– )");
  });

  test("collapses a single-year run", () => {
    expect(seriesYears({ seriesStartYear: 1963, seriesEndYear: 1963 })).toBe(
      "(1963)",
    );
  });

  test("shows an end year with no known start", () => {
    expect(seriesYears({ seriesEndYear: 1996 })).toBe("(–1996)");
  });

  test("shows nothing when neither year is known", () => {
    expect(seriesYears({})).toBe("");
  });
});

export default {};
