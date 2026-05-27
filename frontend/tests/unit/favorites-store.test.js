/*
 * Unit tests for ``stores/favorites.js`` — the per-user favorites
 * cache. Focuses on the contract the UI consumes:
 *
 * - hydrate() parses the per-group ``{p:[...], i:[...], ...}`` shape
 *   into reactive Sets the ``isFavorite`` getter can probe.
 * - toggle() optimistically flips the local Set and fires the
 *   matching PUT/DELETE; rolls back on error so the UI never lies.
 * - clear() resets state on logout/user-switch.
 *
 * The HTTP client is mocked so the store can be exercised without a
 * Pinia/axios bootstrap. Each test re-installs a fresh Pinia so
 * state doesn't leak across cases.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/v4/favorites", () => ({
  getFavorites: vi.fn(),
  addFavorite: vi.fn(),
  removeFavorite: vi.fn(),
}));

import * as API from "@/api/v4/favorites";
import { useFavoritesStore } from "@/stores/favorites";

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(API)) {
    fn.mockReset();
  }
});

describe("useFavoritesStore — initial state", () => {
  it("starts with empty Sets for every favorite-able group", () => {
    const store = useFavoritesStore();
    for (const group of ["p", "i", "s", "v", "f", "a", "c"]) {
      expect(store.favoriteIds[group]).toBeInstanceOf(Set);
      expect(store.favoriteIds[group].size).toBe(0);
    }
    expect(store.hydrated).toBe(false);
  });

  it("isFavorite returns false for any (group, pk) before hydration", () => {
    const store = useFavoritesStore();
    expect(store.isFavorite("s", 1)).toBe(false);
    expect(store.isFavorite("c", 99)).toBe(false);
  });

  it("isFavorite returns false for an unknown group code", () => {
    const store = useFavoritesStore();
    expect(store.isFavorite("z", 1)).toBe(false);
  });
});

describe("useFavoritesStore — hydrate", () => {
  it("populates per-group Sets from the API payload", async () => {
    API.getFavorites.mockResolvedValue({
      data: { p: [], i: [], s: [42, 7], v: [], f: [], a: [], c: [101] },
    });
    const store = useFavoritesStore();
    await store.hydrate();
    expect(store.hydrated).toBe(true);
    expect(store.isFavorite("s", 42)).toBe(true);
    expect(store.isFavorite("s", 7)).toBe(true);
    expect(store.isFavorite("s", 999)).toBe(false);
    expect(store.isFavorite("c", 101)).toBe(true);
  });

  it("ignores groups missing from the payload", async () => {
    /*
     * Defensive: if the backend ever ships a partial payload (e.g.,
     * an older server), absent groups stay empty Sets rather than
     * undefined. The getter should still return false cleanly.
     */
    API.getFavorites.mockResolvedValue({ data: { s: [1] } });
    const store = useFavoritesStore();
    await store.hydrate();
    expect(store.isFavorite("s", 1)).toBe(true);
    expect(store.isFavorite("c", 1)).toBe(false);
    expect(store.favoriteIds.c).toBeInstanceOf(Set);
  });

  it("swallows API errors without leaving the store partially mutated", async () => {
    API.getFavorites.mockRejectedValue(new Error("boom"));
    const store = useFavoritesStore();
    await store.hydrate();
    expect(store.hydrated).toBe(false);
    expect(store.favoriteIds.s.size).toBe(0);
  });
});

describe("useFavoritesStore — toggle", () => {
  it("favorites a previously-unfavorited row via PUT", async () => {
    API.addFavorite.mockResolvedValue({});
    const store = useFavoritesStore();
    expect(store.isFavorite("s", 5)).toBe(false);

    const promise = store.toggle("s", 5);
    // Optimistic: state is flipped before the API resolves.
    expect(store.isFavorite("s", 5)).toBe(true);
    await promise;
    expect(store.isFavorite("s", 5)).toBe(true);
    expect(API.addFavorite).toHaveBeenCalledWith("s", 5);
    expect(API.removeFavorite).not.toHaveBeenCalled();
  });

  it("unfavorites a favorited row via DELETE", async () => {
    API.removeFavorite.mockResolvedValue({});
    const store = useFavoritesStore();
    store.favoriteIds.s.add(5);

    const promise = store.toggle("s", 5);
    expect(store.isFavorite("s", 5)).toBe(false);
    await promise;
    expect(store.isFavorite("s", 5)).toBe(false);
    expect(API.removeFavorite).toHaveBeenCalledWith("s", 5);
    expect(API.addFavorite).not.toHaveBeenCalled();
  });

  it("rolls back the optimistic add when PUT rejects", async () => {
    API.addFavorite.mockRejectedValue(new Error("server down"));
    const store = useFavoritesStore();
    await store.toggle("s", 5);
    expect(store.isFavorite("s", 5)).toBe(false);
  });

  it("rolls back the optimistic remove when DELETE rejects", async () => {
    API.removeFavorite.mockRejectedValue(new Error("server down"));
    const store = useFavoritesStore();
    store.favoriteIds.s.add(5);
    await store.toggle("s", 5);
    expect(store.isFavorite("s", 5)).toBe(true);
  });

  it("no-ops on an unknown group code", async () => {
    const store = useFavoritesStore();
    await store.toggle("z", 1);
    expect(API.addFavorite).not.toHaveBeenCalled();
    expect(API.removeFavorite).not.toHaveBeenCalled();
  });
});

describe("useFavoritesStore — clear", () => {
  it("wipes Sets and resets the hydrated flag", async () => {
    API.getFavorites.mockResolvedValue({
      data: { p: [], i: [], s: [1, 2], v: [], f: [], a: [], c: [3] },
    });
    const store = useFavoritesStore();
    await store.hydrate();
    expect(store.hydrated).toBe(true);
    expect(store.favoriteIds.s.size).toBe(2);
    store.clear();
    expect(store.hydrated).toBe(false);
    for (const group of ["p", "i", "s", "v", "f", "a", "c"]) {
      expect(store.favoriteIds[group].size).toBe(0);
    }
  });
});
