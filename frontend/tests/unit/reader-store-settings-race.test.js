/*
 * Reader settings responses land only on the book or scope they were for.
 *
 * Every settings action awaits the server and then writes to whatever book
 * or series scope is open at that moment. Change a setting and turn to the
 * next book before the save returns, and the old book's settings were
 * written onto the new one; a slow load for a book already left behind
 * could overwrite the settings of the book now open.
 */
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as READER_API from "@/api/v4/reader";
import { useReaderStore } from "@/stores/reader";

const book = (pk, settings = {}) => ({ pk, maxPage: 10, settings });

// A request the test settles by hand, after changing books.
const deferred = (api, method) => {
  const { promise, resolve } = Promise.withResolvers();
  vi.spyOn(api, method).mockReturnValue(promise);
  return resolve;
};

const readerOn = (current) => {
  const store = useReaderStore();
  store.books = { current, prev: false, next: false };
  return store;
};

const SERIES_7 = Object.freeze({ scopeType: "series", scopePk: 7, name: "A" });
const SERIES_8 = Object.freeze({ scopeType: "series", scopePk: 8, name: "B" });

const readerInSeries7 = () => {
  const store = readerOn(book(3));
  store.intermediateInfo = { ...SERIES_7 };
  store.intermediateSettings = { twoPages: false };
  return store;
};

describe("reader settings responses after the book changes", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("applies a comic settings save to the book still open", async () => {
    const store = readerOn(book(3));
    const resolve = deferred(READER_API, "updateSettings");

    const saving = store.updateComicSettings({ fitTo: "W" });
    resolve({});
    await saving;

    expect(store.books.current.settings).toStrictEqual({ fitTo: "W" });
  });

  it("drops a comic settings save for a book already left", async () => {
    const store = readerOn(book(3));
    const resolve = deferred(READER_API, "updateSettings");

    const saving = store.updateComicSettings({ fitTo: "W" });
    store.books = {
      current: book(4, { fitTo: "H" }),
      prev: false,
      next: false,
    };
    resolve({});
    await saving;

    expect(store.books.current.settings).toStrictEqual({ fitTo: "H" });
  });

  it("drops a comic settings reset for a book already left", async () => {
    const store = readerOn(book(3, { fitTo: "W" }));
    const resolve = deferred(READER_API, "resetSettings");

    const clearing = store.clearComicSettings();
    store.books = {
      current: book(4, { fitTo: "H" }),
      prev: false,
      next: false,
    };
    resolve({});
    await clearing;

    expect(store.books.current.settings).toStrictEqual({ fitTo: "H" });
  });

  it("drops a settings load for a book already left", async () => {
    const store = readerOn(book(3));
    const resolve = deferred(READER_API, "getSettings");

    const loading = store.loadAllSettings(3);
    store.books = {
      current: book(4, { fitTo: "H" }),
      prev: false,
      next: false,
    };
    resolve({
      data: {
        scopes: { comics: { fitTo: "W" }, series: { twoPages: true } },
        scopeInfo: { series: { pk: 7, name: "A" } },
      },
    });
    await loading;

    expect(store.books.current.settings).toStrictEqual({ fitTo: "H" });
    expect(store.intermediateInfo).toBeNull();
  });

  it("applies a settings load for the book still open", async () => {
    const store = readerOn(book(3));
    const resolve = deferred(READER_API, "getSettings");

    const loading = store.loadAllSettings(3);
    resolve({
      data: {
        scopes: { comics: { fitTo: "W" }, series: { twoPages: true } },
        scopeInfo: { series: { pk: 7, name: "A" } },
      },
    });
    await loading;

    expect(store.books.current.settings).toStrictEqual({ fitTo: "W" });
    expect(store.intermediateSettings).toStrictEqual({ twoPages: true });
    expect(store.intermediateInfo).toStrictEqual(SERIES_7);
  });
});

describe("series settings responses after the series changes", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("applies a series settings save to the series still open", async () => {
    const store = readerInSeries7();
    const resolve = deferred(READER_API, "updateSettings");

    const saving = store.updateIntermediateSettings({ twoPages: true });
    resolve({});
    await saving;

    expect(store.intermediateSettings).toStrictEqual({ twoPages: true });
  });

  it.each([
    ["save", "updateSettings", (store) => store.updateIntermediateSettings({})],
    ["reset", "resetSettings", (store) => store.clearIntermediateSettings()],
  ])(
    "drops a series settings %s for a series already left",
    async (_label, method, act) => {
      const store = readerInSeries7();
      const resolve = deferred(READER_API, method);

      const pending = act(store);
      store.intermediateInfo = { ...SERIES_8 };
      store.intermediateSettings = { fitTo: "H" };
      resolve({});
      await pending;

      expect(store.intermediateSettings).toStrictEqual({ fitTo: "H" });
    },
  );
});
