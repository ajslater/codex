import { defineStore } from "pinia";

import * as API from "@/api/v4/favorites";

const FAVORITE_COLLECTION_CODES = Object.freeze([
  "publishers",
  "imprints",
  "series",
  "volumes",
  "folders",
  "arcs",
  "comics",
]);

function emptyFavoriteIds() {
  const ids = {};
  for (const collection of FAVORITE_COLLECTION_CODES) {
    ids[collection] = new Set();
  }
  return ids;
}

export const useFavoritesStore = defineStore("favorites", {
  state: () => ({
    favoriteIds: emptyFavoriteIds(),
    hydrated: false,
  }),
  getters: {
    /*
     * Curried so callers can spread the getter into a computed
     * without recomputing on every dependency change. Example:
     *   isFavorite: (state) => (collection, pk) => ...
     * lets ``isFavorite(collection, pk)`` track only the matching Set.
     */
    isFavorite: (state) => (collection, pk) => {
      const set = state.favoriteIds[collection];
      return Boolean(set && set.has(pk));
    },
  },
  actions: {
    async hydrate() {
      try {
        const response = await API.getFavorites();
        const data = response.data || {};
        const next = emptyFavoriteIds();
        for (const collection of FAVORITE_COLLECTION_CODES) {
          const ids = data[collection];
          if (Array.isArray(ids)) {
            next[collection] = new Set(ids);
          }
        }
        this.$patch({
          favoriteIds: next,
          hydrated: true,
        });
      } catch (error) {
        console.error(error);
      }
    },
    async toggle(collection, pk) {
      const set = this.favoriteIds[collection];
      if (!set) {
        console.error(`Unknown favorite collection ${collection}`);
        return;
      }
      /*
       * Optimistic flip: mutate locally, fire the matching API call,
       * and roll back if the server rejects so the UI never lies.
       */
      const wasFavorite = set.has(pk);
      this._setLocal(collection, pk, !wasFavorite);
      const apiCall = wasFavorite ? API.removeFavorite : API.addFavorite;
      try {
        await apiCall(collection, pk);
      } catch (error) {
        this._setLocal(collection, pk, wasFavorite);
        console.error(error);
      }
    },
    _setLocal(collection, pk, on) {
      const set = this.favoriteIds[collection];
      if (!set) return;
      if (on) {
        set.add(pk);
      } else {
        set.delete(pk);
      }
    },
    clear() {
      /*
       * Logout / user switch — wipe the cached Sets so a different
       * user doesn't see the previous account's favorite stars.
       */
      this.$patch({
        favoriteIds: emptyFavoriteIds(),
        hydrated: false,
      });
    },
  },
});
