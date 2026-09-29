/*
 * How the reader masks its settings scopes into one book's settings.
 *
 * ``getBookSettings`` layers the book's own settings over the series,
 * folder or arc settings over the global settings, derives the reading
 * direction flags and the fit class, and caches the result per book. Every
 * action that changes an input to that mask must drop the cache, or the
 * pages keep drawing with the old settings. ``fitToClass`` reads the zoom
 * scale, so a zoom is one of those inputs.
 */
import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import * as READER_API from "@/api/v4/reader";
import { SCALE_DEFAULT, useReaderStore } from "@/stores/reader";

const book = (pk, settings = {}) => ({ pk, maxPage: 10, settings });

const GLOBAL = Object.freeze({
  fitTo: "S",
  twoPages: false,
  readingDirection: "ltr",
  cacheBook: true,
  pageTransition: true,
});

const SERIES_7 = Object.freeze({ scopeType: "series", scopePk: 7, name: "A" });

const readerOn = (current, intermediate = {}) => {
  const store = useReaderStore();
  store.globalSettings = { ...GLOBAL };
  store.intermediateSettings = intermediate;
  store.books = { current, prev: false, next: false };
  return store;
};

describe("reader store getBookSettings mask", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("layers the book over the series over the global settings", () => {
    const store = readerOn(book(3, { fitTo: "W" }), {
      fitTo: "H",
      twoPages: true,
    });

    const settings = store.getBookSettings(store.books.current);

    expect(settings.fitTo).toBe("W");
    expect(settings.twoPages).toBe(true);
    expect(settings.readingDirection).toBe("ltr");
  });

  it.each([
    ["an empty string", ""],
    ["null", null],
    ["undefined", undefined],
  ])("never lets %s override a lower scope", (_label, value) => {
    const store = readerOn(book(3, { fitTo: value }), { fitTo: value });

    expect(store.getBookSettings(store.books.current).fitTo).toBe("S");
  });

  it.each([
    ["false", false],
    ["0", 0],
  ])("lets %s override a lower scope", (_label, value) => {
    const store = readerOn(book(3, { cacheBook: value }));

    expect(store.getBookSettings(store.books.current).cacheBook).toBe(value);
  });

  it.each([
    ["ltr", true],
    ["rtl", true],
    ["ttb", false],
    ["btt", false],
  ])("reading %s keeps two pages: %s", (readingDirection, twoPages) => {
    const store = readerOn(book(3, { readingDirection }), { twoPages: true });

    expect(store.getBookSettings(store.books.current).twoPages).toBe(twoPages);
  });

  it.each([
    ["ltr", false, false],
    ["rtl", false, true],
    ["ttb", true, false],
    ["btt", true, true],
  ])(
    "reading %s is vertical: %s, reversed: %s",
    (readingDirection, isVertical, isReadInReverse) => {
      const store = readerOn(book(3, { readingDirection }));

      expect(store.getBookSettings(store.books.current)).toMatchObject({
        isVertical,
        isReadInReverse,
      });
      expect(store.isVertical).toBe(isVertical);
      expect(store.isReadInReverse).toBe(isReadInReverse);
    },
  );
});

describe("reader store fitToClass", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it.each([
    [
      "fits to the setting at the default scale",
      SCALE_DEFAULT,
      {},
      "fitToScreen",
    ],
    [
      "shows the original size setting at the default scale",
      SCALE_DEFAULT,
      { fitTo: "O" },
      "fitToOrig",
    ],
    [
      "shows two pages at the original size setting",
      SCALE_DEFAULT,
      { fitTo: "O", twoPages: true },
      "fitToOrigTwo",
    ],
    [
      "shows vertical pages at the original size setting",
      SCALE_DEFAULT,
      { fitTo: "O", readingDirection: "ttb" },
      "fitToOrigVertical",
    ],
    ["shows the original size zoomed in", SCALE_DEFAULT + 0.5, {}, "fitToOrig"],
    [
      "shows two original pages zoomed in",
      SCALE_DEFAULT + 0.5,
      { twoPages: true },
      "fitToOrigTwo",
    ],
    [
      "shows vertical original pages zoomed in",
      SCALE_DEFAULT + 0.5,
      { readingDirection: "ttb" },
      "fitToOrigVertical",
    ],
  ])("%s", (_label, scale, settings, fitToClass) => {
    const store = readerOn(book(3, settings));
    store.clientSettings.scale = scale;

    expect(store.getBookSettings(store.books.current).fitToClass).toStrictEqual(
      { [fitToClass]: true },
    );
  });
});

describe("reader store book settings cache", () => {
  let current;
  let store;

  beforeEach(() => {
    setActivePinia(createPinia());
    vi.spyOn(READER_API, "getSettings").mockResolvedValue({
      data: { scopes: { global: {} } },
    });
    vi.spyOn(READER_API, "updateSettings").mockResolvedValue({ data: {} });
    vi.spyOn(READER_API, "resetSettings").mockResolvedValue({ data: {} });
    vi.spyOn(READER_API, "getReaderInfo").mockImplementation(async () => ({
      data: {
        books: { current: book(3), prev: false, next: false },
        arcs: {},
        arc: { collection: "series", ids: [] },
        mtime: 1,
      },
    }));
    current = book(3);
    store = readerOn(current);
    store.intermediateInfo = { ...SERIES_7 };
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the cached settings without recomputing them", () => {
    const first = store.getBookSettings(current);
    const fitToClass = vi.spyOn(store, "fitToClass");

    expect(store.getBookSettings(current)).toBe(first);
    expect(fitToClass).not.toHaveBeenCalled();
  });

  it.each([
    ["_applyGlobalSettings", (reader) => reader._applyGlobalSettings({})],
    ["seedGlobalDefaults", (reader) => reader.seedGlobalDefaults({})],
    ["reset", (reader) => reader.reset()],
    ["loadGlobalSettings", (reader) => reader.loadGlobalSettings()],
    [
      "loadBooks",
      (reader) => reader.loadBooks({ params: { pk: 3, page: 0 }, mtime: 1 }),
    ],
    ["loadAllSettings", (reader) => reader.loadAllSettings(3)],
    [
      "updateComicSettings",
      (reader) => reader.updateComicSettings({ fitTo: "H" }),
    ],
    ["clearComicSettings", (reader) => reader.clearComicSettings()],
    [
      "updateIntermediateSettings",
      (reader) => reader.updateIntermediateSettings({ fitTo: "H" }),
    ],
    [
      "clearIntermediateSettings",
      (reader) => reader.clearIntermediateSettings(),
    ],
    [
      "updateGlobalSettings",
      (reader) => reader.updateGlobalSettings({ fitTo: "H" }),
    ],
    ["clearGlobalSettings", (reader) => reader.clearGlobalSettings()],
    [
      "setSettingsClient",
      (reader) => reader.setSettingsClient({ scale: SCALE_DEFAULT + 0.5 }),
    ],
  ])("is dropped by %s", async (_action, act) => {
    const cached = store.getBookSettings(current);

    await act(store);

    expect(store.getBookSettings(current)).not.toBe(cached);
  });

  it("switches the fit class when the reader zooms", () => {
    expect(store.getBookSettings(current).fitToClass).toStrictEqual({
      fitToScreen: true,
    });

    store.setSettingsClient({ scale: SCALE_DEFAULT + 0.5 });

    expect(store.getBookSettings(current).fitToClass).toStrictEqual({
      fitToOrig: true,
    });
  });
});

describe("reader store loadBooks settings request", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loads every settings scope, global included, in one request", async () => {
    const { promise, resolve } = Promise.withResolvers();
    const getSettings = vi
      .spyOn(READER_API, "getSettings")
      .mockReturnValue(promise);
    vi.spyOn(READER_API, "getReaderInfo").mockResolvedValue({
      data: {
        books: { current: book(3), prev: false, next: false },
        arcs: {},
        arc: { collection: "series", ids: [] },
        mtime: 1,
      },
    });
    const store = useReaderStore();

    await store.loadBooks({ params: { pk: 3, page: 0 }, mtime: 1 });
    resolve({ data: { scopes: { global: { fitTo: "O" } } } });

    expect(getSettings).toHaveBeenCalledExactlyOnceWith(
      3,
      ["global", "series", "comics"],
      null,
    );
    await vi.waitFor(() => {
      expect(store.globalSettings.fitTo).toBe("O");
    });
  });

  it("keeps the site defaults off the global settings it loaded", async () => {
    vi.spyOn(READER_API, "getSettings").mockResolvedValue({
      data: { scopes: { global: { fitTo: "O" } } },
    });
    vi.spyOn(READER_API, "getReaderInfo").mockResolvedValue({
      data: {
        books: { current: book(3), prev: false, next: false },
        arcs: {},
        arc: { collection: "series", ids: [] },
        mtime: 1,
      },
    });
    const store = useReaderStore();

    await store.loadBooks({ params: { pk: 3, page: 0 }, mtime: 1 });
    await vi.waitFor(() => {
      expect(store.globalSettings.fitTo).toBe("O");
    });

    expect(store.seedGlobalDefaults({ fitTo: "H" })).toBe(false);
    expect(store.globalSettings.fitTo).toBe("O");
  });
});
