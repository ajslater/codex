/*
 * Regression tests for the search-clear collection redirect in
 * ``stores/browser.js`` (``_validateSearch``).
 *
 * Entering a search redirects the browser *down* to
 * ``lowestShownCollection`` (e.g. the series root). Clearing the search
 * must redirect back *out* to the top collection — otherwise the user is
 * stranded at a deep collection root with no parent breadcrumbs / no
 * "up" arrows, while the top-collection setting still reads "publishers".
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

// ``liveBrowseParams()`` (module scope in browser.js) reads
// ``router.currentRoute.value``; mock the router so tests can place the
// browser at an arbitrary collection / parentIds without a real router.
vi.mock("@/plugins/router", () => ({
  default: { currentRoute: { value: { params: {}, query: {} } } },
}));

import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";

const setRoute = (collection, parentIds) => {
  router.currentRoute.value = {
    params: parentIds ? { collection, parentIds } : { collection },
    query: {},
  };
};

const makeStore = () => {
  const store = useBrowserStore();
  // volumes hidden -> lowestShownCollection resolves to "series"
  store.settings.topCollection = "publishers";
  store.settings.show = {
    publishers: true,
    imprints: true,
    series: true,
    volumes: false,
  };
  return store;
};

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("browser store _validateSearch — clearing search", () => {
  it("redirects to the top collection when clearing from the search-redirected root", () => {
    const store = makeStore();
    store.settings.search = "batman"; // a search is active
    setRoute("series"); // ...which sent us down to the series root
    expect(store.lowestShownCollection).toBe("series");

    const redirect = store._validateSearch({ search: "" });

    expect(redirect).toStrictEqual({
      params: { collection: "root", pks: "", page: "1" },
    });
  });

  it("does not redirect when clearing from a deep (non-root) collection", () => {
    const store = makeStore();
    store.settings.search = "batman";
    setRoute("series", "5"); // navigated into a container; has breadcrumbs

    const redirect = store._validateSearch({ search: "" });

    expect(redirect).toBeUndefined();
  });

  it("does not redirect for a non-search settings change while search is active", () => {
    const store = makeStore();
    store.settings.search = "batman";
    setRoute("series");

    // ``data`` has no ``search`` key -> still in search mode, stay put.
    const redirect = store._validateSearch({ orderBy: "sort_name" });

    expect(redirect).toBeUndefined();
  });

  it("still redirects down to lowestShownCollection on the first search", () => {
    const store = makeStore();
    store.settings.search = ""; // no active search yet
    setRoute("publishers"); // at the top (resolves to "root")

    const redirect = store._validateSearch({ search: "batman" });

    expect(redirect).toStrictEqual({
      params: { collection: "series", pks: "", page: "1" },
    });
  });
});
