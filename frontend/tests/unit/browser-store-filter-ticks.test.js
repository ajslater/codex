/*
 * Ticking filter values with the filter menu open.
 *
 * A tick patches the filter at once and reloads the page in place after a
 * short wait, so a quick run of ticks is one request; an aborted request
 * still runs to the end on the server. Settings are saved once the load
 * succeeds. While the menu is open a page load keeps its choices on
 * screen and marks them stale, rather than emptying them under the open
 * sub-menu. Fake timers throughout: a real-timer debounce test raced
 * under load before (#916).
 */
import { createTestingPinia } from "@pinia/testing";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("@/plugins/router", () => ({
  default: {
    currentRoute: {
      value: {
        params: { collection: "series", parentIds: "7", page: "3" },
        query: {},
      },
    },
    push: vi.fn(() => Promise.resolve()),
  },
}));

vi.mock("@/api/v4/browser", async (importOriginal) => ({
  ...(await importOriginal()),
  getBrowserHead: vi.fn(),
  getBrowserPage: vi.fn(),
  getFilterChoices: vi.fn(),
  updateSettings: vi.fn(() => Promise.resolve()),
}));

import * as API from "@/api/v4/browser";
import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";

const WAIT = 200;
const PAGE = Object.freeze({ data: { breadcrumbs: [], books: [], mtime: 5 } });
const CHOICES = Object.freeze({ characters: Object.freeze([{ pk: 1 }]) });

function storeWith({
  filterMenuOpen = true,
  filterMode = "characters",
  browserPageLoaded = true,
} = {}) {
  createTestingPinia({
    stubActions: false,
    initialState: {
      auth: { user: { pk: 1 } },
      browser: {
        browserPageLoaded,
        filterMenuOpen,
        filterMode,
        choices: { dynamic: CHOICES },
        page: { mtime: 4, count: 10 },
        settings: {
          breadcrumbs: [],
          filters: { bookmark: "", characters: [] },
          show: {},
          topCollection: "series",
          viewMode: "cover",
        },
      },
    },
  });
  return useBrowserStore();
}

beforeEach(() => {
  vi.useFakeTimers();
  for (const mock of [
    API.getBrowserHead,
    API.getBrowserPage,
    API.getFilterChoices,
    API.updateSettings,
    router.push,
  ]) {
    mock.mockClear();
  }
  API.getBrowserPage.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("a tick", () => {
  test("patches the filter at once and leaves the sub-menu open", () => {
    const store = storeWith();
    store.tickFilters({ characters: [1] });
    expect(store.settings.filters.characters).toEqual([1]);
    expect(store.filterMode).toBe("characters");
    expect(API.getBrowserPage).not.toHaveBeenCalled();
  });

  test("a quick run of ticks makes one page request", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    store.tickFilters({ characters: [1] });
    await vi.advanceTimersByTimeAsync(WAIT / 2);
    store.tickFilters({ characters: [1, 2] });
    await vi.advanceTimersByTimeAsync(WAIT / 2);
    store.tickFilters({ characters: [1, 2, 3] });
    await vi.advanceTimersByTimeAsync(WAIT);
    expect(API.getBrowserPage).toHaveBeenCalledOnce();
    const [, settings] = API.getBrowserPage.mock.calls[0];
    expect(settings.filters.characters).toEqual([1, 2, 3]);
  });

  test("reloads in place, without the loading placeholder", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    const loaded = [];
    store.$subscribe((_mutation, state) => {
      loaded.push(state.browserPageLoaded);
    });
    store.tickFilters({ characters: [1] });
    await vi.advanceTimersByTimeAsync(WAIT);
    expect(store.page.mtime).toBe(5);
    expect(loaded).not.toContain(false);
  });

  test("saves the settings once the page loads", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    store.tickFilters({ characters: [1] });
    await vi.advanceTimersByTimeAsync(WAIT);
    expect(API.updateSettings).toHaveBeenCalledOnce();
    expect(API.updateSettings.mock.calls[0][0].filters.characters).toEqual([1]);
  });

  test("saves nothing when the page fails", async () => {
    API.getBrowserPage.mockRejectedValue({ response: { status: 500 } });
    vi.spyOn(console, "error").mockImplementation(() => {});
    const store = storeWith();
    store.tickFilters({ characters: [1] });
    await vi.advanceTimersByTimeAsync(WAIT);
    expect(API.updateSettings).not.toHaveBeenCalled();
  });

  test("on a page that no longer exists, follows the redirect", async () => {
    vi.spyOn(console, "debug").mockImplementation(() => {});
    const route = {
      name: "browser",
      params: { collection: "series", pks: "7", page: 1 },
    };
    API.getBrowserPage.mockRejectedValue({
      response: { status: 303, data: { route, settings: null } },
    });
    const store = storeWith();
    store.tickFilters({ characters: [1] });
    await vi.advanceTimersByTimeAsync(WAIT);
    expect(router.push).toHaveBeenCalledOnce();
    expect(store.filterMode).toBe("characters");
    expect(store.choices.dynamic).toEqual(CHOICES);
  });
});

describe("a page load and the filter menu's choices", () => {
  test("with the menu open, keeps them and marks them stale", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    await store.loadBrowserPage();
    expect(store.choices.dynamic).toEqual(CHOICES);
    expect(store.choicesStale).toBe(true);
  });

  test("with the menu closed, empties them as before", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith({ filterMenuOpen: false, filterMode: "base" });
    await store.loadBrowserPage();
    expect(store.choices.dynamic).toBeUndefined();
    expect(store.choicesStale).toBe(false);
  });

  test("closing the menu resets the mode and empties stale choices", () => {
    const store = storeWith();
    store.choicesStale = true;
    store.setFilterMenuOpen(false);
    expect(store.filterMode).toBe("base");
    expect(store.choices.dynamic).toBeUndefined();
    expect(store.choicesStale).toBe(false);
  });

  test("settings changes leave the sub-menu alone", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    await store.setSettings({ filters: { characters: [1] } });
    expect(store.filterMode).toBe("characters");
  });
});

describe("late answers", () => {
  test("a filter's choices are not written into emptied choices", async () => {
    const { promise, resolve } = Promise.withResolvers();
    API.getFilterChoices.mockReturnValue(promise);
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const store = storeWith({ filterMenuOpen: false });
    const loading = store.loadFilterChoices("characters");
    store.choices.dynamic = undefined;
    resolve({ data: { choices: [{ pk: 2 }] } });
    await loading;
    expect(store.choices.dynamic).toBeUndefined();
    expect(error).not.toHaveBeenCalled();
  });

  test("a library check during a page load is skipped", async () => {
    const { promise, resolve } = Promise.withResolvers();
    API.getBrowserPage.mockReturnValue(promise);
    const store = storeWith();
    const loading = store.loadBrowserPage();
    await store.loadMtimes();
    expect(API.getBrowserHead).not.toHaveBeenCalled();
    resolve(PAGE);
    await loading;
  });

  test("after a failed page load, a library check loads the page again", async () => {
    // Nothing is in flight: the next library change is how it recovers.
    API.getBrowserHead.mockResolvedValue({ data: { mtime: 5, count: 10 } });
    const store = storeWith({ browserPageLoaded: false });
    const load = vi.spyOn(store, "loadBrowserPage").mockResolvedValue();
    await store.loadMtimes();
    expect(API.getBrowserHead).toHaveBeenCalledOnce();
    expect(load).toHaveBeenCalledWith(5);
  });

  test("a tick made while the library check is out stops its full load", async () => {
    const { promise, resolve } = Promise.withResolvers();
    API.getBrowserHead.mockReturnValue(promise);
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    const loaded = [];
    store.$subscribe((_mutation, state) => {
      loaded.push(state.browserPageLoaded);
    });
    const checking = store.loadMtimes();
    await vi.advanceTimersByTimeAsync(0);
    store.tickFilters({ characters: [1] });
    resolve({ data: { mtime: 5, count: 10 } });
    await checking;
    await vi.advanceTimersByTimeAsync(WAIT);
    expect(API.getBrowserPage).toHaveBeenCalledOnce();
    expect(loaded).not.toContain(false);
    expect(API.updateSettings).toHaveBeenCalledOnce();
  });

  test("a library check while a tick waits is skipped", async () => {
    API.getBrowserPage.mockResolvedValue(PAGE);
    const store = storeWith();
    store.tickFilters({ characters: [1] });
    await store.loadMtimes();
    expect(API.getBrowserHead).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(WAIT);
    API.getBrowserHead.mockResolvedValue({ data: { mtime: 5, count: 0 } });
    await store.loadMtimes();
    expect(API.getBrowserHead).toHaveBeenCalledOnce();
  });
});
