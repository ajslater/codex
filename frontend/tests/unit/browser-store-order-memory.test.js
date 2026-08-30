/*
 * Tests for the per-top-collection sort memory in ``stores/browser.js``
 * (issue #415).
 *
 * Each top collection remembers the sort it was last browsed with, so
 * switching between them — or leaving and returning from a search —
 * hands that sort back instead of dragging one global sort everywhere.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ``liveBrowseParams()`` (module scope in browser.js) reads
// ``router.currentRoute.value``; mock the router so the store can be
// driven without a real one.
vi.mock("@/plugins/router", () => ({
  default: { currentRoute: { value: { params: {}, query: {} } } },
}));

import { useBrowserStore } from "@/stores/browser";

const ADDED_TIME = {
  orderBy: "created_at",
  orderReverse: true,
  orderExtraKeys: [],
};

const makeStore = (settings = {}) => {
  const store = useBrowserStore();
  store.settings.topCollection = "publishers";
  store.settings.orderBy = "sort_name";
  store.settings.orderReverse = false;
  store.settings.orderExtraKeys = [];
  store.settings.search = "";
  store.settings.collectionOrderMemory = {};
  store.settings.show = {
    publishers: true,
    imprints: true,
    series: true,
    volumes: false,
  };
  Object.assign(store.settings, settings);
  return store;
};

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("collection order memory — switching top collections", () => {
  it("files the sort the old collection is left in", () => {
    const store = makeStore({ orderBy: "created_at", orderReverse: true });
    const data = { topCollection: "comics" };

    store._validateAndSaveSettings(data);

    expect(data.collectionOrderMemory.publishers).toStrictEqual(ADDED_TIME);
  });

  it("hands back the sort the new collection was last browsed with", () => {
    const store = makeStore({
      collectionOrderMemory: { comics: ADDED_TIME },
    });
    const data = { topCollection: "comics" };

    store._validateAndSaveSettings(data);

    expect(data.orderBy).toBe("created_at");
    expect(data.orderReverse).toBe(true);
    expect(data.orderExtraKeys).toStrictEqual([]);
  });

  it("keeps the current sort for a collection with nothing filed", () => {
    const store = makeStore({ orderBy: "created_at", orderReverse: true });
    const data = { topCollection: "comics" };

    store._validateAndSaveSettings(data);

    expect(data.orderBy).toBeUndefined();
    expect(store.settings.orderBy).toBe("created_at");
  });

  it("round-trips a sort back to the collection it came from", () => {
    const store = makeStore({ orderBy: "created_at", orderReverse: true });

    // Leave issues for publishers...
    store.settings.topCollection = "comics";
    const toPublishers = { topCollection: "publishers" };
    store._validateAndSaveSettings(toPublishers);
    store.settings.orderBy = "sort_name";
    store.settings.orderReverse = false;

    // ...then come back.
    const toComics = { topCollection: "comics" };
    store._validateAndSaveSettings(toComics);

    expect(toComics.orderBy).toBe("created_at");
    expect(toComics.orderReverse).toBe(true);
  });

  it("leaves a payload that carries its own sort alone", () => {
    // Settings loads, saved views and redirects all arrive this way.
    const store = makeStore({
      collectionOrderMemory: { comics: ADDED_TIME },
    });
    const data = {
      topCollection: "comics",
      orderBy: "sort_name",
      orderReverse: false,
    };

    store._validateAndSaveSettings(data);

    expect(data.orderBy).toBe("sort_name");
    expect(data.collectionOrderMemory).toBeUndefined();
  });

  it("ignores a settings change that isn't a collection switch", () => {
    const store = makeStore();
    const data = { orderBy: "created_at", orderReverse: true };

    store._validateAndSaveSettings(data);

    expect(data.collectionOrderMemory).toBeUndefined();
  });

  it("does not disturb an active search", () => {
    const store = makeStore({
      search: "batman",
      orderBy: "search_score",
      orderReverse: true,
      collectionOrderMemory: { comics: ADDED_TIME },
    });
    const data = { topCollection: "comics" };

    store._validateAndSaveSettings(data);

    expect(data.orderBy).toBeUndefined();
    // Relevance ordering is never filed against the collection either.
    expect(data.collectionOrderMemory?.publishers).toBeUndefined();
  });
});

describe("collection order memory — around a search", () => {
  it("files the sort a search displaces and hands it back on clear", () => {
    const store = makeStore({ orderBy: "created_at", orderReverse: true });

    const searching = { search: "batman" };
    store._validateSearch(searching);
    expect(searching.collectionOrderMemory.publishers).toStrictEqual(
      ADDED_TIME,
    );
    expect(searching.orderBy).toBe("search_score");

    // The store now looks like it does mid-search.
    store.settings.search = "batman";
    store.settings.orderBy = "search_score";
    store.settings.orderReverse = true;
    store.settings.collectionOrderMemory = searching.collectionOrderMemory;

    const clearing = { search: "" };
    store._validateSearch(clearing);

    expect(clearing.orderBy).toBe("created_at");
    expect(clearing.orderReverse).toBe(true);
  });

  it("falls back to the collection default when nothing was filed", () => {
    const store = makeStore({ search: "batman", orderBy: "search_score" });

    const clearing = { search: "" };
    store._validateSearch(clearing);

    expect(clearing.orderBy).toBe("sort_name");
    expect(clearing.orderReverse).toBe(false);
  });

  it("falls back to filename in folders", () => {
    const store = makeStore({
      topCollection: "folders",
      search: "batman",
      orderBy: "search_score",
    });

    const clearing = { search: "" };
    store._validateSearch(clearing);

    expect(clearing.orderBy).toBe("filename");
  });

  it("cleans up a stale relevance sort left behind by a cleared search", () => {
    const store = makeStore({
      search: "",
      orderBy: "search_score",
      collectionOrderMemory: { publishers: ADDED_TIME },
    });

    const data = {};
    store._validateSearch(data);

    expect(data.orderBy).toBe("created_at");
  });
});
