/*
 * The settings sent with Mark Read, Force Update and metadata loads carry
 * only the filters in use.
 *
 * ``_filterSettings`` used to build a pruned ``filters`` object and then
 * return the original, because ``Array#filter`` only reads the callback's
 * result as a keep/drop flag. Every empty filter list went over the wire.
 * The server treats a missing filter as unset, so pruning changes the
 * request, not the result.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import { useBrowserStore } from "@/stores/browser";

const storeWith = (settings) => {
  const store = useBrowserStore();
  store.settings = { ...store.settings, ...settings };
  return store;
};

describe("browser store filter settings", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("sends only the filters in use", () => {
    const store = storeWith({
      filters: { bookmark: "", characters: [], favorite: false, genres: [5] },
      q: "batman",
    });

    expect(store.filterOnlySettings).toStrictEqual({
      filters: { favorite: false, genres: [5] },
      q: "batman",
    });
  });

  it("drops the filters key when no filter is in use", () => {
    const store = storeWith({
      filters: { bookmark: "", characters: [], genres: [] },
      q: "",
    });

    expect(store.filterOnlySettings).toStrictEqual({});
  });

  it("prunes the same way for metadata loads", () => {
    const store = storeWith({
      filters: { bookmark: "UNREAD", characters: [], genres: [] },
      q: "",
    });

    expect(store.metadataSettings).toStrictEqual({
      filters: { bookmark: "UNREAD" },
    });
  });
});
