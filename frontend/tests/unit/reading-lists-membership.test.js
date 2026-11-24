/*
 * The list menus' half of ``stores/reading-lists.js``, ported from the
 * shelves store when shelves folded into reading lists:
 *
 * - loadMyLists() / hydrate() parse ``{lists: [{pk, name, items}]}`` into
 *   per-list Sets the ``membershipState`` / ``isEveryListed`` getters
 *   probe; hydrate(userId) clears another user's lists first and drops a
 *   late response for a user who is gone.
 * - setTargetsMembership() flips the Sets at once and sends one PATCH;
 *   it rolls back on error, and undoes only what the server refused.
 *   Changes to one list run one at a time, in order.
 * - removeFromList() offers to remove the series a comic comes through.
 * - createList() rejects with the server's reason; deleteList() takes the
 *   list out of the browser's Reading Lists filter.
 */
import { flushPromises } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/v4/reading-lists", () => ({
  createList: vi.fn(),
  deleteList: vi.fn(),
  getMyLists: vi.fn(),
  updateItems: vi.fn(),
}));

import { APIError } from "@/api/v4/base";
import * as API from "@/api/v4/reading-lists";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";
import {
  LIST_ITEM_COLLECTIONS,
  useReadingListsStore,
} from "@/stores/reading-lists";

const PAYLOAD = {
  lists: [
    {
      pk: 1,
      name: "Favorites",
      personal: true,
      count: 3,
      editable: true,
      items: { series: [42, 7], comics: [101] },
    },
    {
      pk: 2,
      name: "Want to Read",
      personal: true,
      count: 1,
      editable: true,
      items: { series: [7], comics: [] },
    },
  ],
};

async function loaded() {
  API.getMyLists.mockResolvedValue({ data: structuredClone(PAYLOAD) });
  const store = useReadingListsStore();
  await store.loadMyLists();
  return store;
}

const has = (store, collection, id) =>
  store.myLists.find((list) => list.pk === 1).items[collection].has(id);

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(API)) {
    fn.mockReset();
  }
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("loading", () => {
  it("builds a Set per collection for every list", async () => {
    const store = await loaded();
    for (const list of store.myLists) {
      for (const collection of LIST_ITEM_COLLECTIONS) {
        // Collections missing from the payload are empty Sets.
        expect(list.items[collection]).toBeInstanceOf(Set);
      }
    }
    expect(has(store, "series", 42)).toBe(true);
    expect(store.myLists[0].count).toBe(3);
  });

  it("keeps no lists when the server fails", async () => {
    API.getMyLists.mockRejectedValue(new Error("boom"));
    const store = useReadingListsStore();
    await store.loadMyLists();
    expect(store.myLists).toEqual([]);
  });

  it("clears the last user's lists before hydrating another's", async () => {
    API.getMyLists.mockResolvedValueOnce({ data: structuredClone(PAYLOAD) });
    const store = useReadingListsStore();
    await store.hydrate(1);
    expect(store.myLists).toHaveLength(2);
    API.getMyLists.mockReturnValueOnce(new Promise(() => {}));
    void store.hydrate(2);
    expect(store.myLists).toEqual([]);
  });

  it("keeps the lists while the same user rehydrates", async () => {
    API.getMyLists.mockResolvedValueOnce({ data: structuredClone(PAYLOAD) });
    const store = useReadingListsStore();
    await store.hydrate(1);
    API.getMyLists.mockReturnValueOnce(new Promise(() => {}));
    void store.hydrate(1);
    expect(store.myLists).toHaveLength(2);
  });

  it("drops a late response for the last user", async () => {
    const late = Promise.withResolvers();
    API.getMyLists.mockReturnValueOnce(late.promise);
    const store = useReadingListsStore();
    const first = store.hydrate(1);
    API.getMyLists.mockResolvedValueOnce({ data: { lists: [] } });
    await store.hydrate(2);
    late.resolve({ data: structuredClone(PAYLOAD) });
    await first;
    expect(store.myLists).toEqual([]);
  });

  it("clear() drops the lists and their owner", async () => {
    const store = await loaded();
    store.clear();
    expect(store.myLists).toEqual([]);
    expect(store.myListsLoaded).toBe(false);
  });
});

describe("getters", () => {
  it("membershipState reports all / some / none across collections", async () => {
    const store = await loaded();
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

  it("isEveryListed needs every target in at least one list", async () => {
    const store = await loaded();
    expect(store.isEveryListed({ series: [42, 7], comics: [101] })).toBe(true);
    expect(store.isEveryListed({ series: [42, 999] })).toBe(false);
    expect(store.isEveryListed({})).toBe(false);
  });

  it("myListNames are the user's own lists", async () => {
    const store = await loaded();
    store.myLists.push({
      ...store.myLists[0],
      pk: 3,
      name: "G",
      personal: false,
    });
    expect(store.myListNames).toEqual(["Favorites", "Want to Read"]);
  });
});

describe("setTargetsMembership", () => {
  it("adds what the list lacks with one PATCH, and takes the new count", async () => {
    API.updateItems.mockResolvedValue({ data: { refused: [], count: 9 } });
    const store = await loaded();

    const promise = store.setTargetsMembership(1, { series: [42, 8, 9] }, true);
    // Optimistic: flipped before the server answers.
    expect(has(store, "series", 8)).toBe(true);
    expect(await promise).toBe(true);

    expect(store.membershipState(1, { series: [42, 8, 9] })).toBe("all");
    // 42 was already in the list, so it isn't sent again.
    expect(API.updateItems).toHaveBeenCalledExactlyOnceWith(1, {
      add: { series: [8, 9] },
    });
    expect(store.myLists[0].count).toBe(9);
    expect(store.membershipVersion).toBe(1);
  });

  it("removes what the list holds with one PATCH", async () => {
    API.updateItems.mockResolvedValue({ data: {} });
    const store = await loaded();
    await store.setTargetsMembership(1, { series: [42, 999] }, false);
    expect(has(store, "series", 42)).toBe(false);
    expect(API.updateItems).toHaveBeenCalledExactlyOnceWith(1, {
      remove: { series: [42] },
    });
  });

  it("sends every collection of a mixed selection in one PATCH", async () => {
    API.updateItems.mockResolvedValue({ data: {} });
    const store = await loaded();
    await store.setTargetsMembership(
      2,
      { series: [7, 42], comics: [101], publishers: [3] },
      true,
    );
    expect(API.updateItems).toHaveBeenCalledExactlyOnceWith(2, {
      add: { series: [42], comics: [101], publishers: [3] },
    });
  });

  it("sends nothing when every target is already in the wanted state", async () => {
    const store = await loaded();
    expect(await store.setTargetsMembership(1, { series: [42, 7] }, true)).toBe(
      true,
    );
    expect(API.updateItems).not.toHaveBeenCalled();
    expect(store.membershipVersion).toBe(0);
  });

  it("rolls back only what it flipped when the PATCH rejects", async () => {
    API.updateItems.mockRejectedValue(new Error("server down"));
    const store = await loaded();
    expect(await store.setTargetsMembership(1, { series: [42, 8] }, true)).toBe(
      false,
    );
    expect(has(store, "series", 8)).toBe(false);
    // In the list before the call; the rollback must not take it out.
    expect(has(store, "series", 42)).toBe(true);
    expect(store.membershipVersion).toBe(0);
  });

  it("undoes a refused target and says why", async () => {
    API.updateItems.mockResolvedValue({
      data: {
        refused: [
          { collection: "arcs", pk: 1, reason: "A list cannot hold itself." },
        ],
      },
    });
    const store = await loaded();
    await store.setTargetsMembership(1, { arcs: [1], series: [8] }, true);
    expect(has(store, "arcs", 1)).toBe(false);
    expect(has(store, "series", 8)).toBe(true);
    expect(useCommonStore().notice).toMatchObject({
      text: "A list cannot hold itself.",
      error: true,
    });
  });

  it("runs overlapping changes to one list in order", async () => {
    const firstPatch = Promise.withResolvers();
    API.updateItems
      .mockReturnValueOnce(firstPatch.promise)
      .mockResolvedValue({ data: {} });
    const store = await loaded();

    const first = store.setTargetsMembership(1, { series: [8] }, true);
    const second = store.setTargetsMembership(1, { series: [8] }, false);
    await flushPromises();
    // The second waits for the first, so the server sees them in order.
    expect(API.updateItems).toHaveBeenCalledOnce();

    firstPatch.resolve({ data: {} });
    expect(await first).toBe(true);
    expect(await second).toBe(true);
    expect(API.updateItems).toHaveBeenNthCalledWith(2, 1, {
      remove: { series: [8] },
    });
    expect(has(store, "series", 8)).toBe(false);
  });

  it("doesn't hold one list's change for another's", async () => {
    API.updateItems
      .mockReturnValueOnce(new Promise(() => {}))
      .mockResolvedValue({ data: {} });
    const store = await loaded();
    void store.setTargetsMembership(1, { series: [8] }, true);
    expect(await store.setTargetsMembership(2, { series: [8] }, true)).toBe(
      true,
    );
    expect(API.updateItems).toHaveBeenCalledTimes(2);
  });

  it("no-ops on an unknown list or collection", async () => {
    const store = await loaded();
    expect(await store.setTargetsMembership(99, { series: [1] }, true)).toBe(
      false,
    );
    expect(await store.setTargetsMembership(1, { nope: [1] }, true)).toBe(true);
    expect(API.updateItems).not.toHaveBeenCalled();
  });
});

describe("removeFromList", () => {
  const ITEM = Object.freeze({
    pk: 5,
    collection: "series",
    targetId: 7,
    label: "Daredevil",
  });

  it("says what went", async () => {
    API.updateItems.mockResolvedValue({
      data: { removed: 1, hidden: 1, refused: [], count: 1 },
    });
    const store = await loaded();
    expect(await store.removeFromList(1, [101])).toBe(true);
    expect(API.updateItems).toHaveBeenCalledExactlyOnceWith(1, {
      remove: { comics: [101] },
    });
    expect(useCommonStore().notice.text).toBe(
      "Removed 1 comic, hid 1 comic its sources hold from the list.",
    );
    expect(store.myLists[0].count).toBe(1);
  });

  it("offers to remove the series an issue comes through", async () => {
    API.updateItems.mockResolvedValueOnce({
      data: { removed: 0, hidden: 0, refused: [{ comic: 101, item: ITEM }] },
    });
    const store = await loaded();
    const browserStore = useBrowserStore();
    browserStore.refreshBrowserPage = vi.fn();
    expect(await store.removeFromList(1, [101])).toBe(false);

    const { notice } = useCommonStore();
    expect(notice.text).toBe("That issue is in this list through Daredevil.");
    expect(notice.action.label).toBe("Remove Daredevil");

    API.updateItems.mockResolvedValueOnce({ data: { removed: 1, count: 0 } });
    await notice.action.run();
    expect(API.updateItems).toHaveBeenLastCalledWith(1, {
      remove: { series: [7] },
    });
    expect(has(store, "series", 7)).toBe(false);
    expect(useCommonStore().notice.text).toBe(
      "Removed Daredevil from the list.",
    );
    expect(browserStore.refreshBrowserPage).toHaveBeenCalledOnce();
  });

  it("names every item when issues come through several", async () => {
    const other = { ...ITEM, pk: 6, targetId: 8, label: "X-Men" };
    API.updateItems.mockResolvedValue({
      data: {
        removed: 0,
        hidden: 0,
        refused: [
          { comic: 101, item: ITEM },
          { comic: 102, item: other },
        ],
      },
    });
    const store = await loaded();
    await store.removeFromList(1, [101, 102]);
    const { notice } = useCommonStore();
    expect(notice.text).toBe(
      "2 of those issues are in this list through Daredevil and X-Men. Remove those instead.",
    );
    expect(notice.action).toBeUndefined();
  });
});

describe("create and delete", () => {
  it("createList resolves to the store's copy of the new list", async () => {
    const store = await loaded();
    API.createList.mockResolvedValue({ data: { pk: 3, name: "Reading Now" } });
    API.getMyLists.mockResolvedValue({
      data: {
        lists: [
          ...structuredClone(PAYLOAD.lists),
          { pk: 3, name: "Reading Now", personal: true, editable: true },
        ],
      },
    });
    const list = await store.createList("Reading Now");
    expect(API.createList).toHaveBeenCalledWith("Reading Now");
    expect(list.pk).toBe(3);
    expect(list.items.comics).toBeInstanceOf(Set);
  });

  it("createList rejects with the server's reason", async () => {
    const refusal = new APIError(
      {
        status: "400",
        title: "Bad Request",
        detail: "You already have a reading list with that name.",
      },
      400,
    );
    API.createList.mockRejectedValue(refusal);
    const store = await loaded();
    await expect(store.createList("Favorites")).rejects.toBe(refusal);
  });

  it("deleteList takes the list out of the browser's filter", async () => {
    API.deleteList.mockResolvedValue({});
    const store = await loaded();
    const browserStore = useBrowserStore();
    browserStore.settings.filters = { bookmark: "", readingLists: [2, 1] };
    browserStore.setSettings = vi.fn();
    expect(await store.deleteList(1)).toBe(true);
    expect(browserStore.setSettings).toHaveBeenCalledExactlyOnceWith({
      filters: { readingLists: [2] },
    });
  });

  it("deleteList leaves an unfiltered browser alone", async () => {
    API.deleteList.mockResolvedValue({});
    const store = await loaded();
    const browserStore = useBrowserStore();
    browserStore.setSettings = vi.fn();
    await store.deleteList(1);
    expect(browserStore.setSettings).not.toHaveBeenCalled();
  });
});
