/*
 * ``refreshBrowserPage`` refetches the shown page in place: unlike
 * ``loadBrowserPage`` it never drops ``browserPageLoaded``, which is what
 * swaps the table for the loading placeholder and remounts it (closing any
 * open menu). It stays out of the way of a full load already in flight.
 */
import { createTestingPinia } from "@pinia/testing";
import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/plugins/router", () => ({
  default: {
    currentRoute: {
      value: { params: { collection: "series", parentIds: "7" }, query: {} },
    },
    push: vi.fn(() => Promise.resolve()),
  },
}));

vi.mock("@/api/v4/browser", async (importOriginal) => ({
  ...(await importOriginal()),
  getBrowserPage: vi.fn(),
}));

import * as API from "@/api/v4/browser";
import { useBrowserStore } from "@/stores/browser";

function storeWith({ browserPageLoaded = true } = {}) {
  createTestingPinia({
    stubActions: false,
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        browserPageLoaded,
        page: Object.freeze({ rows: [{ pk: 1, readingLists: [] }] }),
        settings: {
          breadcrumbs: [],
          show: {},
          tableColumns: { publishers: ["name", "reading_lists"] },
          topCollection: "publishers",
          viewMode: "table",
        },
      },
    },
  });
  return useBrowserStore();
}

beforeEach(() => {
  API.getBrowserPage.mockReset();
});

describe("refreshBrowserPage", () => {
  test("swaps in the fresh page without the loading placeholder", async () => {
    API.getBrowserPage.mockResolvedValue({
      data: { breadcrumbs: [], rows: [{ pk: 1, readingLists: ["Mine"] }] },
    });
    const store = storeWith();
    const loaded = [];
    store.$subscribe((_mutation, state) => {
      loaded.push(state.browserPageLoaded);
    });

    await store.refreshBrowserPage();

    expect(store.page.rows).toEqual([{ pk: 1, readingLists: ["Mine"] }]);
    expect(store.browserPageLoaded).toBe(true);
    expect(loaded).not.toContain(false);
    const [, settings] = API.getBrowserPage.mock.calls[0];
    expect(settings.columns).toBe("name,reading_lists");
  });

  test("leaves a full load in flight alone", async () => {
    const store = storeWith({ browserPageLoaded: false });
    await store.refreshBrowserPage();
    expect(API.getBrowserPage).not.toHaveBeenCalled();
  });
});
