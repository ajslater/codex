/*
 * READING_LISTS_CHANGED reaches every user: their own lists reload, and an
 * admin's table too while it is on screen; the tab loads afresh when it
 * opens. Nothing that was never loaded is fetched.
 */
import { createTestingPinia } from "@pinia/testing";
import { setActivePinia } from "pinia";
import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/plugins/router", () => ({
  default: { currentRoute: { value: { name: "admin-reading-lists" } } },
}));

vi.mock("@/api/v4/reading-lists", () => ({
  getAdminLists: vi.fn(),
  getMyLists: vi.fn(),
  getSuggestions: vi.fn(() => Promise.resolve({ data: { suggestions: [] } })),
}));

import * as API from "@/api/v4/reading-lists";
import router from "@/plugins/router";
import { useAuthStore } from "@/stores/auth";
import { useReadingListsStore } from "@/stores/reading-lists";
import { readingListsNotified } from "@/stores/socket";

function setup({
  admin,
  listsLoaded,
  myListsLoaded,
  route = "admin-reading-lists",
}) {
  router.currentRoute.value = { name: route };
  setActivePinia(createTestingPinia({ createSpy: vi.fn, stubActions: false }));
  const auth = useAuthStore();
  auth.user = admin ? { pk: 1, isStaff: true } : { pk: 2, isStaff: false };
  const store = useReadingListsStore();
  store.listsLoaded = listsLoaded;
  store.myListsLoaded = myListsLoaded;
  return store;
}

describe("reading lists notifications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    API.getAdminLists.mockResolvedValue({ data: { lists: [] } });
    API.getMyLists.mockResolvedValue({ data: { lists: [{ pk: 3 }] } });
  });

  test("a user's own lists reload", async () => {
    const store = setup({
      admin: false,
      listsLoaded: false,
      myListsLoaded: true,
    });
    await readingListsNotified();
    expect(API.getMyLists).toHaveBeenCalledTimes(1);
    expect(API.getAdminLists).not.toHaveBeenCalled();
    expect(store.myLists.map((list) => list.pk)).toEqual([3]);
  });

  test("an admin's table and its suggestions reload too", async () => {
    setup({ admin: true, listsLoaded: true, myListsLoaded: true });
    await readingListsNotified();
    expect(API.getAdminLists).toHaveBeenCalledTimes(1);
    expect(API.getSuggestions).toHaveBeenCalledTimes(1);
    expect(API.getMyLists).toHaveBeenCalledTimes(1);
  });

  test("an admin elsewhere: the table waits for its tab", async () => {
    // The tab loads its table when it opens; a reload off it is wasted.
    setup({
      admin: true,
      listsLoaded: true,
      myListsLoaded: true,
      route: "reader",
    });
    await readingListsNotified();
    expect(API.getAdminLists).not.toHaveBeenCalled();
    expect(API.getMyLists).toHaveBeenCalledTimes(1);
  });

  test("nothing loaded, nothing fetched", async () => {
    setup({ admin: false, listsLoaded: false, myListsLoaded: false });
    await readingListsNotified();
    expect(API.getMyLists).not.toHaveBeenCalled();
    expect(API.getAdminLists).not.toHaveBeenCalled();
  });
});
