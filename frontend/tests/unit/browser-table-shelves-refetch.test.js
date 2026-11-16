/*
 * The table refetches its page after a shelf membership change, but only
 * while the Shelves column is showing: the column's shelf lists come from
 * the server (through parents, across a collection's comics) and can't be
 * patched locally.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import BrowserTable from "@/components/browser/table/browser-table.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";
import { useShelvesStore } from "@/stores/shelves";

async function bumpWith(columns) {
  const pinia = createTestingPinia({
    createSpy: vi.fn,
    initialState: {
      browser: { settings: { orderBy: "sort_name" }, page: { rows: [] } },
    },
  });
  const browserStore = useBrowserStore(pinia);
  browserStore._resolveTableColumns.mockReturnValue(columns);
  const wrapper = mount(BrowserTable, {
    global: {
      plugins: [pinia, vuetify],
      stubs: { BrowserEmptyState: true, BrowserTableCell: true },
    },
  });
  useShelvesStore(pinia).membershipVersion += 1;
  await wrapper.vm.$nextTick();
  return browserStore.refreshBrowserPage;
}

describe("browser table shelf refetch", () => {
  test("refetches in place while the Shelves column shows", async () => {
    const refreshBrowserPage = await bumpWith(["name", "shelved"]);
    expect(refreshBrowserPage).toHaveBeenCalledOnce();
  });

  test("leaves the page alone without the column", async () => {
    const refreshBrowserPage = await bumpWith(["name"]);
    expect(refreshBrowserPage).not.toHaveBeenCalled();
  });
});
