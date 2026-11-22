/*
 * The settings sent with Mark Read, Force Update and metadata loads carry
 * only the filters in use.
 *
 * ``_filterSettings`` used to build a pruned ``filters`` object and then
 * return the original, because ``Array#filter`` only reads the callback's
 * result as a keep/drop flag. Every empty filter list went over the wire.
 * The server treats a missing filter as unset, so pruning changes the
 * request, not the result.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useBrowserStore } from "@/stores/browser";

const storeWith = (settings) => {
  const store = useBrowserStore();
  store.settings = { ...store.settings, ...settings };
  return store;
};

describe("browser store filter settings", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("sends only the filters in use", () => {
    const store = storeWith({
      filters: { bookmark: "", characters: [], genres: [5], readingLists: [3] },
      q: "batman",
    });

    expect(store.filterOnlySettings).toStrictEqual({
      filters: { genres: [5], readingLists: [3] },
      q: "batman",
    });
  });

  it("drops the filters key when no filter is in use", () => {
    const store = storeWith({
      filters: { bookmark: "", characters: [], genres: [], readingLists: [] },
      q: "",
    });

    expect(store.filterOnlySettings).toStrictEqual({});
  });

  it("prunes the same way for metadata loads", () => {
    const store = storeWith({
      filters: { bookmark: "UNREAD", characters: [], genres: [] },
      q: "",
    });

    expect(store.metadataSettings).toStrictEqual({
      filters: { bookmark: "UNREAD" },
    });
  });

  it("counts selected lists as a selected, clearable filter", () => {
    const store = storeWith({ filters: { bookmark: "", readingLists: [] } });
    expect(store.isDynamicFiltersSelected).toBe(false);
    expect(store.isFiltersClearable).toBe(false);

    store.settings.filters.readingLists = [3];
    expect(store.isDynamicFiltersSelected).toBe(true);
    expect(store.isFiltersClearable).toBe(true);
  });

  it("counts a picked reading list kind like any filter", () => {
    const store = storeWith({ filters: { bookmark: "", readingListKind: [] } });
    expect(store.isDynamicFiltersSelected).toBe(false);
    expect(store.isFiltersClearable).toBe(false);
    expect(store.filterOnlySettings).toStrictEqual({});

    store.settings.filters.readingListKind = ["mine"];
    expect(store.isDynamicFiltersSelected).toBe(true);
    expect(store.isFiltersClearable).toBe(true);
    expect(store.filterOnlySettings.filters).toStrictEqual({
      readingListKind: ["mine"],
    });
  });
});

describe("browser store setSettings", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("resolves after the page it reloads", async () => {
    /*
     * Callers reload the filter choices after awaiting setSettings; the
     * page load clears them, so it must land first.
     */
    const store = useBrowserStore();
    const { promise: pageLoad, resolve: finishPage } = Promise.withResolvers();
    vi.spyOn(store, "loadBrowserPage").mockReturnValue(pageLoad);
    vi.spyOn(store, "_validateAndSaveSettings").mockReturnValue();
    const settled = vi.fn();

    const done = (async () => {
      await store.setSettings({ filters: { readingLists: [1] } });
      settled();
    })();
    // Drain every pending microtask, Pinia's action wrapper included.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(settled).not.toHaveBeenCalled();

    finishPage();
    await done;
    expect(settled).toHaveBeenCalledOnce();
  });
});
