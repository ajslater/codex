/*
 * Characterization tests for the top-collection logic in
 * ``stores/browser.js``: ``_validateTopCollection``, ``getTopCollection``
 * and the ``lowestShownCollection`` getter.
 *
 * Changing the top collection can leave the browser on a route that no
 * longer fits the hierarchy, so ``_validateTopCollection`` decides whether
 * to redirect: to a collection root, or in place with a numeric page that
 * forces the breadcrumbs to reload. It has needed five fixes (755263621,
 * 1c54f1b5f, 0777f13f0, 540ad92f1, fe16bdb1c) and nothing tested it; these
 * pin what it does today.
 *
 * Routes are named ``collection/parentIds``. A bare ``publishers`` route is
 * the synthetic ``root`` collection.
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

// The route before the browser has one: no collection at all.
const clearRoute = () => {
  router.currentRoute.value = { params: {}, query: {} };
};

const setRoute = (collection, parentIds, page) => {
  router.currentRoute.value = {
    params: parentIds ? { collection, parentIds } : { collection },
    query: page ? { page } : {},
  };
};

// volumes hidden -> lowestShownCollection resolves to "series"
const SHOW = Object.freeze({
  publishers: true,
  imprints: true,
  series: true,
  volumes: false,
});

const makeStore = (settings = {}) => {
  const store = useBrowserStore();
  store.settings.topCollection = "publishers";
  store.settings.search = "";
  store.settings.show = { ...SHOW };
  Object.assign(store.settings, settings);
  return store;
};

const rootOf = (collection) => ({
  params: { collection, pks: "", page: "1" },
});

const ROOT_REDIRECT = rootOf("root");

/*
 * A redirect handed in by ``_validateSearch``. Returning it untouched is how
 * the validator says "no top-collection redirect".
 */
const SEARCH_REDIRECT = Object.freeze(rootOf("series"));

beforeEach(() => {
  setActivePinia(createPinia());
  clearRoute();
});

describe("_validateTopCollection — at the root route", () => {
  it.each(["imprints", "series", "volumes", "comics"])(
    "publishers (root): switching to %s passes the incoming redirect through",
    (topCollection) => {
      const store = makeStore();
      setRoute("publishers");

      const redirect = store._validateTopCollection(
        { topCollection },
        SEARCH_REDIRECT,
      );

      expect(redirect).toBe(SEARCH_REDIRECT);
    },
  );

  it.each(["folders", "arcs"])(
    "publishers (root): switching to %s redirects to that collection's root",
    (topCollection) => {
      const store = makeStore();
      setRoute("publishers");

      const redirect = store._validateTopCollection(
        { topCollection },
        SEARCH_REDIRECT,
      );

      expect(redirect).toStrictEqual(rootOf(topCollection));
    },
  );

  it("publishers (root): _validateAndSaveSettings keeps the folders redirect", () => {
    const store = makeStore();
    setRoute("publishers");

    const redirect = store._validateAndSaveSettings({
      topCollection: "folders",
    });

    expect(redirect).toStrictEqual(rootOf("folders"));
    expect(store.settings.topCollection).toBe("folders");
  });

  it("publishers (root): _validateAndSaveSettings returns no redirect for a browse switch", () => {
    const store = makeStore();
    setRoute("publishers");

    const redirect = store._validateAndSaveSettings({
      topCollection: "series",
    });

    expect(redirect).toBeUndefined();
    expect(store.settings.topCollection).toBe("series");
  });
});

describe("_validateTopCollection — cases that keep the route", () => {
  it("series/5: an unchanged top collection passes the redirect through", () => {
    const store = makeStore();
    setRoute("series", "5");

    const redirect = store._validateTopCollection(
      { topCollection: "publishers" },
      SEARCH_REDIRECT,
    );

    expect(redirect).toBe(SEARCH_REDIRECT);
  });

  it("series/5: a payload without a topCollection passes the redirect through", () => {
    const store = makeStore();
    setRoute("series", "5");

    const redirect = store._validateTopCollection(
      { orderBy: "created_at" },
      SEARCH_REDIRECT,
    );

    expect(redirect).toBe(SEARCH_REDIRECT);
  });

  it("series/5: a top collection matching the route's collection passes the redirect through", () => {
    // publishers -> series would otherwise be a child switch to root.
    const store = makeStore();
    setRoute("series", "5");

    const redirect = store._validateTopCollection(
      { topCollection: "series" },
      SEARCH_REDIRECT,
    );

    expect(redirect).toBe(SEARCH_REDIRECT);
  });

  it("series/5: the first settings load (no old top collection) passes the redirect through", () => {
    const store = makeStore({ topCollection: undefined });
    setRoute("series", "5");

    const redirect = store._validateTopCollection(
      { topCollection: "publishers" },
      SEARCH_REDIRECT,
    );

    expect(redirect).toBe(SEARCH_REDIRECT);
  });

  it("folders/12: a deep link whose settings name folders keeps the route", () => {
    // 0777f13f0: deep links into folders / arcs were redirected away.
    const store = makeStore();
    setRoute("folders", "12");

    const redirect = store._validateAndSaveSettings({
      topCollection: "folders",
    });

    expect(redirect).toBeUndefined();
    expect(store.settings.topCollection).toBe("folders");
  });
});

describe("_validateTopCollection — switching between browse collections", () => {
  it("series/5?page=3: a parent top collection redirects in place with a numeric page", () => {
    const store = makeStore({ topCollection: "series" });
    setRoute("series", "5", "3");

    const redirect = store._validateTopCollection({
      topCollection: "publishers",
    });

    expect(redirect).toStrictEqual({
      params: { collection: "series", pks: "5", page: 3 },
    });
  });

  it("series/5: _validateAndSaveSettings keeps the in-place parent redirect", () => {
    /*
     * The redirect matches the current route except for its numeric page,
     * which is what stops the "already there" dequal from dropping it.
     */
    const store = makeStore({ topCollection: "series" });
    setRoute("series", "5");

    const redirect = store._validateAndSaveSettings({
      topCollection: "publishers",
    });

    expect(redirect).toStrictEqual({
      params: { collection: "series", pks: "5", page: 1 },
    });
    expect(store.settings.topCollection).toBe("publishers");
  });

  it.each(["volumes", "comics"])(
    "series/5: a child top collection (%s) redirects to root",
    (topCollection) => {
      const store = makeStore();
      setRoute("series", "5");

      const redirect = store._validateTopCollection(
        { topCollection },
        SEARCH_REDIRECT,
      );

      expect(redirect).toStrictEqual(ROOT_REDIRECT);
    },
  );

  it("series/5: _validateAndSaveSettings keeps the child switch's root redirect", () => {
    const store = makeStore();
    setRoute("series", "5");

    const redirect = store._validateAndSaveSettings({
      topCollection: "volumes",
    });

    expect(redirect).toStrictEqual(ROOT_REDIRECT);
    expect(store.settings.topCollection).toBe("volumes");
  });
});

describe("_validateTopCollection — folders and arcs", () => {
  it.each([
    ["folders", "12", "publishers"],
    ["arcs", "3", "series"],
  ])(
    "%s/%s: leaving for the %s browse top collection redirects to root",
    (collection, parentIds, topCollection) => {
      const store = makeStore({ topCollection: collection });
      setRoute(collection, parentIds);

      const redirect = store._validateTopCollection({ topCollection });

      expect(redirect).toStrictEqual(ROOT_REDIRECT);
    },
  );

  it("folders/12: switching to arcs redirects to the arcs root", () => {
    const store = makeStore({ topCollection: "folders" });
    setRoute("folders", "12");

    const redirect = store._validateTopCollection({ topCollection: "arcs" });

    expect(redirect).toStrictEqual(rootOf("arcs"));
  });

  it("series/5: switching to folders redirects to the folders root", () => {
    const store = makeStore();
    setRoute("series", "5");

    const redirect = store._validateTopCollection({
      topCollection: "folders",
    });

    expect(redirect).toStrictEqual(rootOf("folders"));
  });
});

describe("_validateTopCollection — no browser route yet", () => {
  it("no route: the first settings load passes the redirect through", () => {
    const store = makeStore({ topCollection: undefined });

    const redirect = store._validateTopCollection(
      { topCollection: "publishers" },
      SEARCH_REDIRECT,
    );

    expect(redirect).toBe(SEARCH_REDIRECT);
  });

  it("no route: is not treated as root, so a child switch redirects to root", () => {
    const store = makeStore();

    const redirect = store._validateTopCollection(
      { topCollection: "series" },
      SEARCH_REDIRECT,
    );

    expect(redirect).toStrictEqual(ROOT_REDIRECT);
  });
});

describe("getTopCollection — any route (reads no route)", () => {
  // imprints and volumes hidden.
  const SPARSE_SHOW = Object.freeze({
    publishers: true,
    imprints: false,
    series: true,
    volumes: false,
  });

  it.each([
    ["series", "series"],
    ["volumes", "series"],
    ["imprints", "publishers"],
    ["folders", "folders"],
    ["arcs", "arcs"],
  ])("maps %s to %s", (collection, expected) => {
    const store = makeStore({ show: { ...SPARSE_SHOW } });

    expect(store.getTopCollection(collection)).toBe(expected);
  });

  it("walks past a level settings.show hides", () => {
    const store = makeStore({ show: { ...SPARSE_SHOW, series: false } });

    expect(store.getTopCollection("volumes")).toBe("publishers");
  });

  it("returns the current top collection even when it is hidden", () => {
    const store = makeStore({
      show: { ...SPARSE_SHOW },
      topCollection: "volumes",
    });

    expect(store.getTopCollection("volumes")).toBe("volumes");
  });
});

describe("lowestShownCollection — any route (reads no route)", () => {
  it.each([
    ["publishers", "series"],
    ["imprints", "series"],
    ["series", "series"],
  ])("top collection %s with volumes hidden gives %s", (top, expected) => {
    const store = makeStore({ topCollection: top });

    expect(store.lowestShownCollection).toBe(expected);
  });

  it("top collection publishers with volumes shown gives volumes", () => {
    const store = makeStore({ show: { ...SHOW, volumes: true } });

    expect(store.lowestShownCollection).toBe("volumes");
  });

  it.each(["folders", "arcs", "comics"])(
    "top collection %s falls through to root",
    (topCollection) => {
      const store = makeStore({ topCollection });

      expect(store.lowestShownCollection).toBe("root");
    },
  );
});
