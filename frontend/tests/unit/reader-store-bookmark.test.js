/*
 * What ``_setBookmarkPage`` puts on the wire.
 *
 * The reader only ever sent ``finished: true``, and the server only ever
 * sets the flag, so a comic read to the end and then paged back through
 * kept ``{page: N, finished: true}``: invisible to Keep Reading for the
 * whole re-read and drawn with the thick FINISHED bar over an almost
 * empty fill.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as BROWSER_API from "@/api/v4/browser";
import { useReaderStore } from "@/stores/reader";

const MAX_PAGE = 10;

const mountStore = (bookmark) => {
  const store = useReaderStore();
  store.books = {
    current: { pk: 3, maxPage: MAX_PAGE, settings: {}, bookmark },
    prev: false,
    next: false,
  };
  return store;
};

const lastUpdates = (spy) => spy.mock.calls.at(-1)[2];

describe("reader store _setBookmarkPage", () => {
  let spy;

  beforeEach(() => {
    setActivePinia(createPinia());
    spy = vi
      .spyOn(BROWSER_API, "updateCollectionBookmarks")
      .mockResolvedValue({});
  });

  it("sends the page alone in the middle of an unfinished book", async () => {
    const store = mountStore({ page: 0, finished: false });

    await store._setBookmarkPage(4);

    expect(lastUpdates(spy)).toEqual({ page: 4 });
  });

  it("finishes the book on its last page", async () => {
    const store = mountStore({ page: 4, finished: false });

    await store._setBookmarkPage(MAX_PAGE);

    expect(lastUpdates(spy)).toEqual({ page: MAX_PAGE, finished: true });
  });

  it("un-finishes a finished book paged backwards", async () => {
    const store = mountStore({ page: MAX_PAGE, finished: true });

    await store._setBookmarkPage(5);

    expect(lastUpdates(spy)).toEqual({ page: 5, finished: false });
  });

  it("un-finishes a book finished earlier in the same session", async () => {
    // ``books`` is only refetched on a book change, so the flag has to be
    // mirrored locally or the store never learns it set it.
    const store = mountStore({ page: 4, finished: false });

    await store._setBookmarkPage(MAX_PAGE);
    await store._setBookmarkPage(5);

    expect(lastUpdates(spy)).toEqual({ page: 5, finished: false });
  });

  it("does not un-finish a marked-read comic just by opening it", async () => {
    /*
     * "Mark Read" from the card menu leaves the bookmark at page 0, so the
     * reader opens the comic on page 0 and ``pager.vue``'s ``created`` writes
     * that restored position immediately. Landing on the page the bookmark
     * already names is a restore, not a page turn.
     */
    const store = mountStore({ page: 0, finished: true });

    await store._setBookmarkPage(0);

    expect(lastUpdates(spy)).toEqual({ page: 0 });
    expect(store.books.current.bookmark.finished).toBe(true);
  });

  it("does not un-finish a book reopened at its recorded position", async () => {
    const store = mountStore({ page: 6, finished: true });

    await store._setBookmarkPage(6);

    expect(lastUpdates(spy)).toEqual({ page: 6 });
  });

  it("un-finishes once the reader moves off the restored page", async () => {
    const store = mountStore({ page: 0, finished: true });

    await store._setBookmarkPage(0);
    await store._setBookmarkPage(1);

    expect(lastUpdates(spy)).toEqual({ page: 1, finished: false });
  });

  it("treats a null bookmark page as page 0", async () => {
    // ``Bookmark.page`` is nullable, so a marked-read comic that was never
    // opened can carry ``page: null``.
    const store = mountStore({ page: null, finished: true });

    await store._setBookmarkPage(0);

    expect(lastUpdates(spy)).toEqual({ page: 0 });
  });

  it("stops sending the flag once the book is un-finished", async () => {
    const store = mountStore({ page: MAX_PAGE, finished: true });

    await store._setBookmarkPage(5);
    await store._setBookmarkPage(6);

    expect(lastUpdates(spy)).toEqual({ page: 6 });
  });

  it("sends the page alone when the book has no bookmark yet", async () => {
    const store = mountStore(null);

    await store._setBookmarkPage(2);

    expect(lastUpdates(spy)).toEqual({ page: 2 });
    expect(store.books.current.bookmark).toEqual({ page: 2, finished: false });
  });

  it("clamps the page into the book", async () => {
    const store = mountStore({ page: 0, finished: false });

    await store._setBookmarkPage(-3);

    expect(lastUpdates(spy)).toEqual({ page: 0 });
  });
});
