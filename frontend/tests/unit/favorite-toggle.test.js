/*
 * Unit tests for ``favorite-toggle.vue`` — the star control shared by
 * browser cards (single ``pk``) and the metadata toolbar (multi-select
 * ``pks``). Covers the one-or-many normalization, the "all favorited"
 * on-state, and that clicks dispatch the right store action: single →
 * ``toggle``, bulk → ``setManyFavorites``. Real Vuetify is mounted so the
 * button click is exercised through the template; store actions are
 * stubbed by createTestingPinia so calls can be asserted.
 */
import { createTestingPinia } from "@pinia/testing";
import { mount } from "@vue/test-utils";
import { describe, expect, test } from "vitest";

import FavoriteToggle from "@/components/favorite-toggle.vue";
import vuetify from "@/plugins/vuetify";
import { useFavoritesStore } from "@/stores/favorites";

function mountToggle(props, { loggedIn = true, favorites = {} } = {}) {
  const pinia = createTestingPinia({
    initialState: { auth: { user: loggedIn ? { pk: 1 } : null } },
    stubActions: true,
  });
  const favoritesStore = useFavoritesStore();
  for (const [collection, pks] of Object.entries(favorites)) {
    for (const pk of pks) {
      favoritesStore.favoriteIds[collection].add(pk);
    }
  }
  const wrapper = mount(FavoriteToggle, {
    global: { plugins: [pinia, vuetify] },
    props,
  });
  return { wrapper, favoritesStore };
}

describe("FavoriteToggle — single pk (browser card)", () => {
  test("on reflects the single pk and click dispatches toggle", async () => {
    const { wrapper, favoritesStore } = mountToggle(
      { collection: "comics", pk: 42 },
      { favorites: { comics: [42] } },
    );
    expect(wrapper.vm.on).toBe(true);
    expect(wrapper.vm.isBulk).toBe(false);

    await wrapper.find("button").trigger("click");
    expect(favoritesStore.toggle).toHaveBeenCalledWith("comics", 42);
    expect(favoritesStore.setManyFavorites).not.toHaveBeenCalled();
  });
});

describe("FavoriteToggle — many pks (metadata toolbar)", () => {
  test("on is true only when every target is favorited", () => {
    const allOn = mountToggle(
      { collection: "series", pks: [1, 2] },
      { favorites: { series: [1, 2] } },
    );
    expect(allOn.wrapper.vm.isBulk).toBe(true);
    expect(allOn.wrapper.vm.on).toBe(true);

    const mixed = mountToggle(
      { collection: "series", pks: [1, 2, 3] },
      { favorites: { series: [1, 2] } },
    );
    expect(mixed.wrapper.vm.on).toBe(false);
  });

  test("bulk-favorites the whole selection when not all are on", async () => {
    const { wrapper, favoritesStore } = mountToggle(
      { collection: "series", pks: [1, 2, 3] },
      { favorites: { series: [1] } },
    );
    await wrapper.find("button").trigger("click");
    expect(favoritesStore.setManyFavorites).toHaveBeenCalledWith(
      "series",
      [1, 2, 3],
      true,
    );
    expect(favoritesStore.toggle).not.toHaveBeenCalled();
  });

  test("bulk-clears the whole selection when all are on", async () => {
    const { wrapper, favoritesStore } = mountToggle(
      { collection: "series", pks: [1, 2] },
      { favorites: { series: [1, 2] } },
    );
    await wrapper.find("button").trigger("click");
    expect(favoritesStore.setManyFavorites).toHaveBeenCalledWith(
      "series",
      [1, 2],
      false,
    );
  });

  test("string pks normalize to numbers", () => {
    const { wrapper } = mountToggle(
      { collection: "series", pks: ["1", "2"] },
      { favorites: { series: [1, 2] } },
    );
    expect(wrapper.vm.targetPks).toEqual([1, 2]);
    expect(wrapper.vm.on).toBe(true);
  });
});

describe("FavoriteToggle — disabled", () => {
  test("anonymous sessions can't favorite", () => {
    const { wrapper } = mountToggle(
      { collection: "series", pks: [1] },
      { loggedIn: false },
    );
    expect(wrapper.vm.disabled).toBe(true);
  });

  test("an empty target list disables the control", () => {
    const { wrapper } = mountToggle({ collection: "series", pks: [] });
    expect(wrapper.vm.targetPks).toEqual([]);
    expect(wrapper.vm.disabled).toBe(true);
  });
});

export default {};
