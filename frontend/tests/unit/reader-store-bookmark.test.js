/*
 * What ``_setBookmarkPage`` puts on the wire.
 *
 * ``finished`` means "was finished at least once". The reader sets it on
 * the last page and never clears it: paging back through a book already
 * read leaves it read, and only the explicit Mark Unread input un-finishes
 * a comic. These pin that, because the tempting "fix" -- clearing the flag
 * whenever the reader is below the last page -- would also un-finish every
 * marked-read comic the moment it was opened, since ``pager.vue``'s
 * ``created`` writes the restored position on every open and a comic marked
 * read from the card menu sits at page 0.
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

  it("leaves a finished book finished when paged backwards", async () => {
    const store = mountStore({ page: MAX_PAGE, finished: true });

    await store._setBookmarkPage(5);

    expect(lastUpdates(spy)).toEqual({ page: 5 });
  });

  it("leaves a marked-read comic finished when it is opened", async () => {
    // "Mark Read" from the card menu leaves the bookmark at page 0, so the
    // reader opens the comic on page 0 and writes that position right away.
    const store = mountStore({ page: 0, finished: true });

    await store._setBookmarkPage(0);

    expect(lastUpdates(spy)).toEqual({ page: 0 });
  });

  it("never sends a false finished flag", async () => {
    const store = mountStore({ page: MAX_PAGE, finished: true });

    await store._setBookmarkPage(5);
    await store._setBookmarkPage(2);
    await store._setBookmarkPage(0);

    for (const call of spy.mock.calls) {
      expect(call[2].finished).not.toBe(false);
    }
  });

  it("clamps the page into the book", async () => {
    const store = mountStore({ page: 0, finished: false });

    await store._setBookmarkPage(-3);

    expect(lastUpdates(spy)).toEqual({ page: 0 });
  });
});
