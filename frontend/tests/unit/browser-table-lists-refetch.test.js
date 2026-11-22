/*
 * The table refetches its page after a list membership change, but only
 * while the Reading Lists column is showing: the column's list names come
 * from the server (through a series or other collection a list holds
 * whole) and can't be patched locally.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test, vi } from "vitest";

import BrowserTable from "@/components/browser/table/browser-table.vue";
import vuetify from "@/plugins/vuetify";
import { useBrowserStore } from "@/stores/browser";
import { useReadingListsStore } from "@/stores/reading-lists";

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
  useReadingListsStore(pinia).membershipVersion += 1;
  await wrapper.vm.$nextTick();
  return browserStore.refreshBrowserPage;
}

describe("browser table list refetch", () => {
  test("refetches in place while the Reading Lists column shows", async () => {
    const refreshBrowserPage = await bumpWith(["name", "reading_lists"]);
    expect(refreshBrowserPage).toHaveBeenCalledOnce();
  });

  test("leaves the page alone without the column", async () => {
    const refreshBrowserPage = await bumpWith(["name"]);
    expect(refreshBrowserPage).not.toHaveBeenCalled();
  });
});
