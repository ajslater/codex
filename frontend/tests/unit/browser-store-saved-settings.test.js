/*
 * Loading a saved view (``loadSavedSettings`` in ``stores/browser.js``).
 *
 * A saved view can carry a different search or top collection than the
 * current one, so the validators may want a new route for it. Staying on
 * the old route instead strands the browser at a bare nav-collection root
 * with no breadcrumbs, or has the server undo the view's top collection to
 * fit the old route.
 */
import { createTestingPinia } from "@pinia/testing";
import { flushPromises } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/plugins/router", () => ({
  default: {
    currentRoute: { value: { params: {}, query: {} } },
    push: vi.fn(() => Promise.resolve()),
  },
}));

vi.mock("@/api/v4/browser", async (importOriginal) => ({
  ...(await importOriginal()),
  getBrowserPage: vi.fn(() => Promise.resolve({ data: { breadcrumbs: [] } })),
  loadSavedSettings: vi.fn(),
  updateSettings: vi.fn(),
}));

import * as API from "@/api/v4/browser";
import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";

// volumes hidden -> lowestShownCollection resolves to "series"
const SHOW = Object.freeze({
  publishers: true,
  imprints: true,
  series: true,
  volumes: false,
});

const TOP = Object.freeze({
  name: "browser",
  params: { collection: "publishers" },
});

const setRoute = (collection, parentIds) => {
  router.currentRoute.value = {
    params: parentIds ? { collection, parentIds } : { collection },
    query: {},
  };
};

const makeStore = (settings = {}) => {
  createTestingPinia({
    stubActions: false,
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        settings: {
          orderBy: "sort_name",
          search: "",
          show: { ...SHOW },
          topCollection: "publishers",
          ...settings,
        },
      },
    },
  });
  return useBrowserStore();
};

// A saved view as the server sends it.
const savedView = (settings = {}) => ({
  filters: { bookmark: "" },
  orderBy: "sort_name",
  orderReverse: false,
  search: "",
  show: { ...SHOW },
  topCollection: "publishers",
  ...settings,
});

const loadSavedView = async (store, settings) => {
  API.loadSavedSettings.mockResolvedValue({
    data: { settings: savedView(settings), filterWarnings: [] },
  });
  await store.loadSavedSettings(7);
  await flushPromises();
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("loadSavedSettings — leaving a search", () => {
  it("leaves the series root the search redirected into", async () => {
    const store = makeStore({ search: "batman", orderBy: "search_score" });
    setRoute("series");

    await loadSavedView(store);

    expect(store.settings.search).toBe("");
    expect(router.push).toHaveBeenCalledExactlyOnceWith(TOP);
    expect(API.getBrowserPage).not.toHaveBeenCalled();
  });

  it("stays inside a series entered during the search", async () => {
    const store = makeStore({ search: "batman", orderBy: "search_score" });
    setRoute("series", "5");

    await loadSavedView(store);

    expect(router.push).not.toHaveBeenCalled();
    expect(API.getBrowserPage).toHaveBeenCalledOnce();
  });

  it("can clear a saved search whose view shows more levels", async () => {
    /*
     * The saved view searches with volumes shown, but the search redirect
     * is picked before its settings land: it goes to /series, not
     * /volumes. Clearing that search must still find its way back up.
     */
    const store = makeStore();
    setRoute("publishers");

    await loadSavedView(store, {
      orderBy: "search_score",
      search: "batman",
      show: { ...SHOW, volumes: true },
    });
    expect(router.push).toHaveBeenLastCalledWith({
      name: "browser",
      params: { collection: "series" },
    });

    setRoute("series");
    await store.setSettings({ search: "" });

    expect(router.push).toHaveBeenLastCalledWith(TOP);
  });
});

describe("loadSavedSettings — another top collection", () => {
  it("goes to the folders root for a folders view loaded at the top", async () => {
    const store = makeStore();
    setRoute("publishers");

    await loadSavedView(store, {
      orderBy: "filename",
      topCollection: "folders",
    });

    expect(store.settings.topCollection).toBe("folders");
    expect(router.push).toHaveBeenCalledExactlyOnceWith({
      name: "browser",
      params: { collection: "folders" },
    });
    expect(API.getBrowserPage).not.toHaveBeenCalled();
  });

  it("goes to the top for a publishers view loaded inside a folder", async () => {
    const store = makeStore({ topCollection: "folders" });
    setRoute("folders", "12");

    await loadSavedView(store);

    expect(store.settings.topCollection).toBe("publishers");
    expect(router.push).toHaveBeenCalledExactlyOnceWith(TOP);
  });

  it("reloads in place when the view fits the current route", async () => {
    const store = makeStore();
    setRoute("series", "5");

    await loadSavedView(store, { orderBy: "created_at" });

    expect(store.settings.orderBy).toBe("created_at");
    expect(router.push).not.toHaveBeenCalled();
    expect(API.getBrowserPage).toHaveBeenCalledOnce();
    expect(API.updateSettings).toHaveBeenCalledOnce();
  });
});
