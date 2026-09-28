import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import BROWSER_DEFAULTS from "@/choices/browser-defaults.json";
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
