/*
 * Unit tests for ``stores/shelves.js`` — the per-user shelves cache.
 * Focuses on the contract the UI consumes:
 *
 * - hydrate() parses ``{shelves: [{pk, name, items}]}`` into per-shelf
 *   reactive Sets the ``isShelved`` / ``shelvesFor`` /
 *   ``membershipState`` getters can probe.
 * - setMembership() / setTargetsMembership() optimistically flip the
 *   local Sets and send one bulk PATCH; roll back on error so the UI
 *   never lies.
 * - createShelf() / renameShelf() / deleteShelf() keep the list ordered
 *   by name, and a deleted shelf leaves the browser's shelf filter.
 * - clear() resets state on logout/user-switch.
 *
 * The HTTP client is mocked so the store can be exercised without a
 * backend. Each test re-installs a fresh Pinia so state doesn't leak
 * across cases.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/v4/shelves", () => ({
  getShelves: vi.fn(),
  createShelf: vi.fn(),
  renameShelf: vi.fn(),
  deleteShelf: vi.fn(),
  updateShelfItems: vi.fn(),
}));

import * as API from "@/api/v4/shelves";
import { useBrowserStore } from "@/stores/browser";
import { SHELF_COLLECTIONS, useShelvesStore } from "@/stores/shelves";

const PAYLOAD = {
  shelves: [
    { pk: 1, name: "Favorites", items: { series: [42, 7], comics: [101] } },
    { pk: 2, name: "Want to Read", items: { series: [7], comics: [] } },
  ],
};

async function hydrated() {
  API.getShelves.mockResolvedValue({ data: structuredClone(PAYLOAD) });
  const store = useShelvesStore();
  await store.hydrate();
  return store;
}

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(API)) {
    fn.mockReset();
  }
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("useShelvesStore — initial state", () => {
  it("starts with no shelves and unhydrated", () => {
    const store = useShelvesStore();
    expect(store.shelves).toEqual([]);
    expect(store.hydrated).toBe(false);
  });

  it("isShelved is false for anything before hydration", () => {
    const store = useShelvesStore();
    expect(store.isShelved("series", 1)).toBe(false);
    expect(store.isShelved("nope", 1)).toBe(false);
    expect(store.shelvesFor("series", [1])).toEqual([]);
  });
});

describe("useShelvesStore — hydrate", () => {
  it("builds a Set per collection for every shelf", async () => {
    const store = await hydrated();
    expect(store.hydrated).toBe(true);
    expect(store.shelves.map((shelf) => shelf.name)).toEqual([
      "Favorites",
      "Want to Read",
    ]);
    for (const shelf of store.shelves) {
      for (const collection of SHELF_COLLECTIONS) {
        // Collections missing from the payload are empty Sets.
        expect(shelf.items[collection]).toBeInstanceOf(Set);
      }
    }
    expect(store.shelves[0].items.series.has(42)).toBe(true);
  });

  it("swallows API errors without marking the store hydrated", async () => {
    API.getShelves.mockRejectedValue(new Error("boom"));
    const store = useShelvesStore();
    await store.hydrate();
    expect(store.hydrated).toBe(false);
    expect(store.shelves).toEqual([]);
  });
});

describe("useShelvesStore — getters", () => {
  it("isShelved is true when the item is on any shelf", async () => {
    const store = await hydrated();
    expect(store.isShelved("series", 42)).toBe(true);
    expect(store.isShelved("series", 7)).toBe(true);
    expect(store.isShelved("comics", 101)).toBe(true);
    expect(store.isShelved("series", 999)).toBe(false);
    expect(store.isShelved("comics", 42)).toBe(false);
  });

  it("shelvesFor returns the shelves holding at least one pk", async () => {
    const store = await hydrated();
    const pks = (collection, ids) =>
      store.shelvesFor(collection, ids).map((shelf) => shelf.pk);
    expect(pks("series", [42])).toEqual([1]);
    expect(pks("series", [42, 7])).toEqual([1, 2]);
    expect(pks("series", [999])).toEqual([]);
    expect(pks("nope", [1])).toEqual([]);
  });

  it("membershipState reports all / some / none across collections", async () => {
    const store = await hydrated();
    expect(store.membershipState(1, { series: [42, 7] })).toBe("all");
    expect(store.membershipState(2, { series: [42, 7] })).toBe("some");
    expect(store.membershipState(2, { series: [42] })).toBe("none");
    expect(store.membershipState(1, { series: [42], comics: [101] })).toBe(
      "all",
    );
    expect(store.membershipState(1, { series: [42], comics: [5] })).toBe(
      "some",
    );
    expect(store.membershipState(1, {})).toBe("none");
    expect(store.membershipState(99, { series: [42] })).toBe("none");
  });

  it("isEveryShelved needs every target on at least one shelf", async () => {
    const store = await hydrated();
    expect(store.isEveryShelved({ series: [42, 7], comics: [101] })).toBe(true);
    expect(store.isEveryShelved({ series: [42, 999] })).toBe(false);
    expect(store.isEveryShelved({})).toBe(false);
  });

  it("itemCount totals a shelf across collections", async () => {
    const store = await hydrated();
    expect(store.itemCount(store.shelves[0])).toBe(3);
    expect(store.itemCount(store.shelves[1])).toBe(1);
  });
});

describe("useShelvesStore — setMembership", () => {
  it("adds the pks not yet on the shelf with one PATCH", async () => {
    API.updateShelfItems.mockResolvedValue({ data: { added: 2, removed: 0 } });
    const store = await hydrated();

    const promise = store.setMembership(1, "series", [42, 8, 9], true);
    // Optimistic: state is flipped before the API resolves.
    expect(store.isShelved("series", 8)).toBe(true);
    expect(await promise).toBe(true);

    expect(store.membershipState(1, { series: [42, 8, 9] })).toBe("all");
    // pk 42 was already on the shelf → not resent.
    expect(API.updateShelfItems).toHaveBeenCalledExactlyOnceWith(1, {
      add: { series: [8, 9] },
    });
  });

  it("removes the pks on the shelf with one PATCH", async () => {
    API.updateShelfItems.mockResolvedValue({ data: { added: 0, removed: 1 } });
    const store = await hydrated();

    await store.setMembership(1, "series", [42, 999], false);

    expect(store.shelves[0].items.series.has(42)).toBe(false);
    // Still on shelf 2, so still shelved somewhere.
    expect(store.isShelved("series", 7)).toBe(true);
    expect(API.updateShelfItems).toHaveBeenCalledExactlyOnceWith(1, {
      remove: { series: [42] },
    });
  });

  it("sends every collection of a mixed selection in one PATCH", async () => {
    API.updateShelfItems.mockResolvedValue({ data: {} });
    const store = await hydrated();

    await store.setTargetsMembership(
      2,
      { series: [7, 42], comics: [101], publishers: [3] },
      true,
    );

    expect(API.updateShelfItems).toHaveBeenCalledExactlyOnceWith(2, {
      add: { series: [42], comics: [101], publishers: [3] },
    });
    expect(
      store.membershipState(2, {
        series: [7, 42],
        comics: [101],
        publishers: [3],
      }),
    ).toBe("all");
  });

  it("sends nothing when every target is already in the wanted state", async () => {
    const store = await hydrated();
    expect(await store.setMembership(1, "series", [42, 7], true)).toBe(true);
    expect(API.updateShelfItems).not.toHaveBeenCalled();
  });

  it("rolls back only what it flipped when the PATCH rejects", async () => {
    API.updateShelfItems.mockRejectedValue(new Error("server down"));
    const store = await hydrated();

    expect(await store.setMembership(1, "series", [42, 8], true)).toBe(false);
    expect(store.shelves[0].items.series.has(8)).toBe(false);
    // Was on the shelf before the call; the rollback must not remove it.
    expect(store.shelves[0].items.series.has(42)).toBe(true);

    expect(await store.setMembership(1, "series", [42], false)).toBe(false);
    expect(store.shelves[0].items.series.has(42)).toBe(true);
  });

  it("no-ops on an unknown shelf or collection", async () => {
    const store = await hydrated();
    expect(await store.setMembership(99, "series", [1], true)).toBe(false);
    expect(await store.setMembership(1, "nope", [1], true)).toBe(true);
    expect(API.updateShelfItems).not.toHaveBeenCalled();
  });
});

describe("useShelvesStore — create / rename / delete", () => {
  it("createShelf inserts the new shelf in name order and returns it", async () => {
    API.createShelf.mockResolvedValue({
      data: { pk: 3, name: "Reading Now", items: {} },
    });
    const store = await hydrated();

    const shelf = await store.createShelf("Reading Now");

    expect(API.createShelf).toHaveBeenCalledWith("Reading Now");
    expect(shelf.pk).toBe(3);
    expect(shelf.items.comics).toBeInstanceOf(Set);
    expect(store.shelfNames).toEqual([
      "Favorites",
      "Reading Now",
      "Want to Read",
    ]);
  });

  it("createShelf resolves undefined when the server refuses", async () => {
    API.createShelf.mockRejectedValue(new Error("duplicate"));
    const store = await hydrated();
    expect(await store.createShelf("Favorites")).toBeUndefined();
    expect(store.shelves).toHaveLength(2);
  });

  it("renameShelf renames and re-sorts", async () => {
    API.renameShelf.mockResolvedValue({ data: { pk: 1, name: "Zebra" } });
    const store = await hydrated();

    expect(await store.renameShelf(1, "Zebra")).toBe(true);

    expect(API.renameShelf).toHaveBeenCalledWith(1, "Zebra");
    expect(store.shelfNames).toEqual(["Want to Read", "Zebra"]);
    // Membership survives the rename.
    expect(store.isShelved("series", 42)).toBe(true);
  });

  it("renameShelf leaves the name alone when the server refuses", async () => {
    API.renameShelf.mockRejectedValue(new Error("duplicate"));
    const store = await hydrated();
    expect(await store.renameShelf(1, "Want to Read")).toBe(false);
    expect(store.shelfNames).toEqual(["Favorites", "Want to Read"]);
  });

  it("deleteShelf removes the shelf", async () => {
    API.deleteShelf.mockResolvedValue({});
    const store = await hydrated();
    const browserStore = useBrowserStore();
    browserStore.setSettings = vi.fn();

    expect(await store.deleteShelf(1)).toBe(true);

    expect(API.deleteShelf).toHaveBeenCalledWith(1);
    expect(store.shelfNames).toEqual(["Want to Read"]);
    expect(store.isShelved("series", 42)).toBe(false);
    // Not selected in the filter → the browser is left alone.
    expect(browserStore.setSettings).not.toHaveBeenCalled();
  });

  it("deleteShelf drops the shelf from the browser's shelf filter", async () => {
    API.deleteShelf.mockResolvedValue({});
    const store = await hydrated();
    const browserStore = useBrowserStore();
    browserStore.settings.filters = { bookmark: "", shelves: [2, 1] };
    browserStore.setSettings = vi.fn();

    await store.deleteShelf(1);

    expect(browserStore.setSettings).toHaveBeenCalledExactlyOnceWith({
      filters: { shelves: [2] },
    });
  });

  it("deleteShelf keeps the shelf when the server refuses", async () => {
    API.deleteShelf.mockRejectedValue(new Error("nope"));
    const store = await hydrated();
    expect(await store.deleteShelf(1)).toBe(false);
    expect(store.shelves).toHaveLength(2);
  });
});

describe("useShelvesStore — clear", () => {
  it("drops the shelves and resets the hydrated flag", async () => {
    const store = await hydrated();
    store.clear();
    expect(store.hydrated).toBe(false);
    expect(store.shelves).toEqual([]);
    expect(store.isShelved("series", 42)).toBe(false);
  });
});
