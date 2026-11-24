/*
 * A reading list changing reaches the browsed page.
 *
 * ``refreshIfShowingLists``: a membership change refreshes a page that
 * shows lists, a list's own or one under a ticked Reading Lists filter,
 * in cover view as well as table. ``syncReadingListsFilter``: a list
 * deleted elsewhere is dropped from the server's stored filter, so a
 * client whose ticked filter still names it reloads its settings, and
 * only then.
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
  getSettings: vi.fn(),
}));

import * as API from "@/api/v4/browser";
import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";

function storeWith({
  readingLists = [],
  collection = "series",
  parentIds = "7",
}) {
  router.currentRoute.value = { params: { collection, parentIds }, query: {} };
  createTestingPinia({
    stubActions: false,
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        browserPageLoaded: true,
        settings: {
          breadcrumbs: [],
          filters: { readingLists },
          show: {},
          topCollection: "publishers",
          viewMode: "cover",
        },
      },
    },
  });
  const store = useBrowserStore();
  store.refreshBrowserPage = vi.fn();
  store.loadSettings = vi.fn();
  return store;
}

beforeEach(() => {
  API.getSettings.mockReset();
});

describe("refreshIfShowingLists", () => {
  test("refreshes a list's own page in cover view", async () => {
    const store = storeWith({ collection: "arcs", parentIds: "5" });
    await store.refreshIfShowingLists();
    expect(store.refreshBrowserPage).toHaveBeenCalledOnce();
  });

  test("refreshes a page under a ticked Reading Lists filter", async () => {
    const store = storeWith({ readingLists: [5] });
    await store.refreshIfShowingLists();
    expect(store.refreshBrowserPage).toHaveBeenCalledOnce();
  });

  test("leaves a page that shows no list alone", async () => {
    const store = storeWith({});
    await store.refreshIfShowingLists();
    expect(store.refreshBrowserPage).not.toHaveBeenCalled();
  });
});

describe("syncReadingListsFilter", () => {
  test("reloads the settings when the server dropped a ticked list", async () => {
    const store = storeWith({ readingLists: [5, 6] });
    API.getSettings.mockResolvedValue({
      data: { filters: { readingLists: [6] } },
    });
    await store.syncReadingListsFilter();
    expect(store.loadSettings).toHaveBeenCalledOnce();
  });

  test("does nothing when every ticked list is still there", async () => {
    const store = storeWith({ readingLists: [6] });
    API.getSettings.mockResolvedValue({
      data: { filters: { readingLists: [6] } },
    });
    await store.syncReadingListsFilter();
    expect(store.loadSettings).not.toHaveBeenCalled();
  });

  test("asks nothing when no list is ticked", async () => {
    const store = storeWith({});
    await store.syncReadingListsFilter();
    expect(API.getSettings).not.toHaveBeenCalled();
  });
});
