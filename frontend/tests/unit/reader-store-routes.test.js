import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

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
    expect(store.toRoute(undefined)).toEqual({});
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
