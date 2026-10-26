import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ``loadBooks`` reads ``router.currentRoute.value``; mock the router so
// tests can place the reader on any book and page.
vi.mock("@/plugins/router", () => ({
  default: { currentRoute: { value: { params: {}, query: {} } } },
}));

import * as READER_API from "@/api/v4/reader";
import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
import router from "@/plugins/router";
import { useReaderStore } from "@/stores/reader";

describe("reader store toRoute", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("carries the page in the query, not as a bare param", () => {
    // The reader route is /read/:pk with no :page segment, and pager.vue
    // reads route.query.page. A bare { params: {pk, page} } drops the page,
    // so every flip used to land back on the cover.
    const store = useReaderStore();
    expect(store.toRoute({ pk: 5, page: 3 })).toEqual({
      name: "reader",
      params: { pk: 5 },
      query: { page: 3 },
    });
  });

  it("returns an empty object when there is no route", () => {
    const store = useReaderStore();
    expect(store.toRoute(false)).toEqual({});
    expect(store.toRoute()).toEqual({});
  });
});

describe("reader store closeBookRoute", () => {
  let codex;

  beforeEach(() => {
    setActivePinia(createPinia());
    codex = globalThis.CODEX;
  });

  afterEach(() => {
    globalThis.CODEX = codex;
  });

  it("closes to the last route the server knows about", () => {
    globalThis.CODEX = {
      LAST_ROUTE: { collection: "series", parentIds: [7], page: 1 },
    };
    const store = useReaderStore();

    expect(store.closeBookRoute).toStrictEqual({
      name: "browser",
      params: { collection: "series", parentIds: "7" },
    });
  });

  it("falls back to the shipped default when the server knows none", () => {
    /*
     * This branch used to read a key the defaults do not have, so the
     * one path meant to keep the reader closable would instead have
     * thrown and taken the render down with it.
     */
    globalThis.CODEX = {};
    const store = useReaderStore();

    expect(() => store.closeBookRoute).not.toThrow();
    expect(store.closeBookRoute).toStrictEqual({
      name: "browser",
      params: { collection: BROWSER_DEFAULTS.lastRoute.collection },
    });
  });
});

describe("reader store routeToDirectionOne", () => {
  /*
   * The one-page step in two-page mode used to write ``this.page += delta``
   * before its bounds check, so "previous" on the first page left the
   * reader on page -1, and every further press drifted further out.
   */
  const MAX_PAGE = 5;

  const readerAt = (page) => {
    const store = useReaderStore();
    store.books.current = { pk: 9, maxPage: MAX_PAGE };
    store.page = page;
    const routeTo = vi.spyOn(store, "_routeTo").mockImplementation(() => {});
    return { routeTo, store };
  };

  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it.each([
    ["prev", 0],
    ["next", MAX_PAGE],
  ])("stays put stepping %s past the edge from page %i", (direction, page) => {
    const { routeTo, store } = readerAt(page);

    store.routeToDirectionOne(direction);
    store.routeToDirectionOne(direction);

    expect(store.page).toBe(page);
    expect(routeTo).not.toHaveBeenCalled();
  });

  it.each([
    ["prev", 2, 1],
    ["next", 2, 3],
  ])("steps %s from page %i to %i", (direction, page, expected) => {
    const { routeTo, store } = readerAt(page);

    store.routeToDirectionOne(direction);

    expect(store.page).toBe(expected);
    expect(routeTo).toHaveBeenCalledExactlyOnceWith({ pk: 9, page: expected });
  });
});

const setRoute = (pk, page) => {
  router.currentRoute.value = {
    params: { pk: String(pk) },
    query: { page: String(page) },
  };
};

describe("reader store loadBooks page routes", () => {
  /*
   * The reader route keeps the page in the query, so ``route.params`` never
   * has one. ``loadBooks`` used to step the page routes from
   * ``params.page``, which left both ``false`` after any reload of the open
   * book (a library change, an arc switch): the next-page link then went to
   * the cover and the arrow keys fell through to the next book.
   */
  const MAX_PAGE = 19;
  const book = (pk) => ({ pk, maxPage: MAX_PAGE, settings: {} });

  const readerOn = (current, page) => {
    vi.spyOn(READER_API, "getSettings").mockResolvedValue({
      data: { scopes: {} },
    });
    vi.spyOn(READER_API, "getReaderInfo").mockImplementation(async (pk) => ({
      data: {
        books: { current: book(+pk), prev: book(+pk - 1), next: false },
        arcs: {},
        arc: { collection: "series", ids: [] },
        mtime: 2,
      },
    }));
    const store = useReaderStore();
    store.books = { current, prev: false, next: false };
    store.page = page;
    return store;
  };

  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each([
    ["a library change", { mtime: 2 }],
    ["an arc switch", { arc: { collection: "arcs", ids: [9] } }],
  ])("steps from the store's page after %s", async (_reason, args) => {
    // The query lags in cacheBook mode, where pages move by pushState.
    setRoute(3, 2);
    const store = readerOn(book(3), 7);

    await store.loadBooks(args);

    expect(store.routes.prev).toStrictEqual({ pk: 3, page: 6 });
    expect(store.routes.next).toStrictEqual({ pk: 3, page: 8 });
  });

  it("steps from the query's page on a book change", async () => {
    // Back to the previous book, which opens on its last page.
    setRoute(2, MAX_PAGE);
    const store = readerOn(book(3), 0);

    await store.loadBooks({ params: { pk: "2" } });

    expect(store.routes.prev).toStrictEqual({ pk: 2, page: MAX_PAGE - 1 });
    expect(store.routes.next).toBe(false);
  });
});
