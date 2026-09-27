/*
 * The browser store's runtime site defaults.
 *
 *   - Table columns resolve per collection: the visitor's own list, else the
 *     admin's site default, else the show-gated registry default.
 *   - "Clear All Filters" treats the site default bookmark filter as clear.
 *   - ``tableColumns`` is replaced whole, so a reset can remove a key.
 *   - The first-paint seed applies only until the stored settings load.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import BROWSER_TABLE_DEFAULT_COLUMNS from "@/choices/browser-table-default-columns.json";
import { useAuthStore } from "@/stores/auth";
import {
  registryTableColumns,
  resolveTableColumns,
  useBrowserStore,
} from "@/stores/browser";

const SHOW = Object.freeze({
  publishers: true,
  imprints: false,
  series: true,
  volumes: false,
});

beforeEach(() => {
  setActivePinia(createPinia());
});

describe("resolveTableColumns", () => {
  const site = Object.freeze({ comics: ["cover", "name"], folders: ["name"] });

  it("prefers the visitor, then the site, then the registry", () => {
    const own = { comics: ["size"] };
    expect(resolveTableColumns("comics", own, SHOW, site)).toEqual(["size"]);
    expect(resolveTableColumns("comics", {}, SHOW, site)).toEqual([
      "cover",
      "name",
    ]);
    expect(resolveTableColumns("series", {}, SHOW, site)).toEqual(
      registryTableColumns("series", SHOW),
    );
  });

  it("a visitor who customized one collection still follows the site for another", () => {
    const own = { comics: ["size"] };
    expect(resolveTableColumns("folders", own, SHOW, site)).toEqual(["name"]);
  });

  it("an empty list counts as unset", () => {
    expect(resolveTableColumns("comics", { comics: [] }, SHOW, site)).toEqual([
      "cover",
      "name",
    ]);
    expect(resolveTableColumns("folders", {}, SHOW, { folders: [] })).toEqual(
      BROWSER_TABLE_DEFAULT_COLUMNS.folders,
    );
  });

  it("the store resolves through the auth store's site defaults", () => {
    useAuthStore().defaults = { browser: { tableColumns: site } };
    const store = useBrowserStore();
    store.settings.topCollection = "folders";
    store.settings.tableColumns = {};
    expect(store._resolveTableColumns()).toEqual(["name"]);
  });
});

describe("isFiltersClearable", () => {
  it("the factory All filter is not clearable", () => {
    const store = useBrowserStore();
    store.settings.filters = { bookmark: "" };
    expect(store.isFiltersClearable).toBe(false);
  });

  it("follows the site default bookmark filter", () => {
    useAuthStore().defaults = { browser: { bookmark: "UNREAD" } };
    const store = useBrowserStore();
    store.settings.filters = { bookmark: "UNREAD" };
    expect(store.isFiltersClearable).toBe(false);
    store.settings.filters = { bookmark: "" };
    expect(store.isFiltersClearable).toBe(true);
  });
});

describe("_addSettings", () => {
  it("replaces tableColumns whole so a key can be removed", () => {
    const store = useBrowserStore();
    store._addSettings({
      tableColumns: { comics: ["cover"], folders: ["name"] },
    });
    store._addSettings({ tableColumns: { folders: ["name"] } });
    expect(store.settings.tableColumns).toEqual({ folders: ["name"] });
    store._addSettings({ tableColumns: {} });
    expect(store.settings.tableColumns).toEqual({});
  });

  it("still merges the other object settings", () => {
    const store = useBrowserStore();
    store._addSettings({ show: { ...SHOW } });
    store._addSettings({ show: { imprints: true } });
    expect(store.settings.show).toEqual({ ...SHOW, imprints: true });
  });
});

describe("seedSiteDefaults", () => {
  const DEFAULTS = Object.freeze({
    topCollection: "folders",
    show: { ...SHOW, imprints: true },
    orderBy: "",
    viewMode: "table",
    bookmark: "UNREAD",
    tableColumns: { folders: ["name"] },
  });

  it("seeds fresh objects and maps the automatic sort", () => {
    const store = useBrowserStore();
    const initialFilters = store.settings.filters;
    expect(store.seedSiteDefaults(DEFAULTS)).toBe(true);
    expect(store.settings.topCollection).toBe("folders");
    expect(store.settings.viewMode).toBe("table");
    expect(store.settings.orderBy).toBe("sort_name");
    expect(store.settings.filters.bookmark).toBe("UNREAD");
    expect(store.settings.show.imprints).toBe(true);
    // The shared initial filters object is never written in place.
    expect(initialFilters.bookmark).toBe("");
    // Not seeded: the resolver reads the site default live.
    expect(store.settings.tableColumns).toEqual({});
  });

  it("never overwrites loaded settings", () => {
    const store = useBrowserStore();
    store.browserSettingsLoaded = true;
    expect(store.seedSiteDefaults(DEFAULTS)).toBe(false);
    expect(store.settings.topCollection).toBe("publishers");
  });
});
