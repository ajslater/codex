/*
 * Regression test for hover-to-lazy-import on the Tags activator.
 *
 * Two bugs once left this feature as dead code (fixed in the commit that
 * added this test):
 *   - lazyImportEnabled read this.stateLazyImportMetadata, but the mapped
 *     auth-store state is named stateLazyImportEnabled, so the guard was
 *     always undefined (falsy) and onMouseEnter never imported.
 *   - the @mouseenter binding was a ternary that yielded a function
 *     reference without ever invoking it.
 *
 * These mount the real Vuetify button and dispatch a DOM mouseenter so the
 * template binding is exercised end-to-end, asserting lazyImport fires only
 * when the lazyImportMetadata admin flag is on and the book is an
 * un-imported comic.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import MetadataActivator from "@/components/metadata/metadata-activator.vue";
import vuetify from "@/plugins/vuetify";
import { useMetadataStore } from "@/stores/metadata";

const COMIC = Object.freeze({ group: "comics", pk: 42, hasMetadata: false });

function mountActivator({ lazyImportMetadata = false, book = COMIC } = {}) {
  const pinia = createTestingPinia({
    initialState: { auth: { adminFlags: { lazyImportMetadata } } },
  });
  const metadataStore = useMetadataStore();
  // Stubbed actions return undefined by default; onMouseEnter chains .then().
  metadataStore.lazyImport.mockResolvedValue();
  const wrapper = mount(MetadataActivator, {
    global: { plugins: [pinia, vuetify] },
    props: { toolbar: false, book },
  });
  return { wrapper, metadataStore };
}

describe("MetadataActivator lazy-import-on-hover", () => {
  test("fires lazyImport on hover when the admin flag is on", async () => {
    const { wrapper, metadataStore } = mountActivator({
      lazyImportMetadata: true,
    });

    await wrapper.find("button").trigger("mouseenter");

    expect(metadataStore.lazyImport).toHaveBeenCalledWith({
      group: "comics",
      ids: [42],
    });

    await flushPromises();
    expect(wrapper.vm.lazyImportStarted).toBe(true);
  });

  test("does not fire when the admin flag is off", async () => {
    const { wrapper, metadataStore } = mountActivator({
      lazyImportMetadata: false,
    });

    await wrapper.find("button").trigger("mouseenter");

    expect(metadataStore.lazyImport).not.toHaveBeenCalled();
  });

  test("does not fire for comics that already have metadata", async () => {
    const { wrapper, metadataStore } = mountActivator({
      lazyImportMetadata: true,
      book: { group: "comics", pk: 7, hasMetadata: true },
    });

    await wrapper.find("button").trigger("mouseenter");

    expect(metadataStore.lazyImport).not.toHaveBeenCalled();
  });

  test("does not fire for non-comic groups", async () => {
    const { wrapper, metadataStore } = mountActivator({
      lazyImportMetadata: true,
      book: { group: "series", pk: 7, hasMetadata: false },
    });

    await wrapper.find("button").trigger("mouseenter");

    expect(metadataStore.lazyImport).not.toHaveBeenCalled();
  });

  test("prefers book.ids over book.pk and only imports once", async () => {
    const { wrapper, metadataStore } = mountActivator({
      lazyImportMetadata: true,
      book: { group: "comics", pk: 42, ids: [1, 2, 3], hasMetadata: false },
    });

    const button = wrapper.find("button");
    await button.trigger("mouseenter");
    await flushPromises();
    await button.trigger("mouseenter");

    expect(metadataStore.lazyImport).toHaveBeenCalledTimes(1);
    expect(metadataStore.lazyImport).toHaveBeenCalledWith({
      group: "comics",
      ids: [1, 2, 3],
    });
  });
});

export default {};
