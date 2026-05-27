import { defineStore } from "pinia";

import * as API from "@/api/v4/favorites";

const FAVORITE_GROUP_CODES = Object.freeze(["p", "i", "s", "v", "f", "a", "c"]);

function emptyFavoriteIds() {
  const ids = {};
  for (const group of FAVORITE_GROUP_CODES) {
    ids[group] = new Set();
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
     *   isFavorite: (state) => (group, pk) => ...
     * lets ``isFavorite(group, pk)`` track only the matching Set.
     */
    isFavorite: (state) => (group, pk) => {
      const set = state.favoriteIds[group];
      return Boolean(set && set.has(pk));
    },
  },
  actions: {
    async hydrate() {
      try {
        const response = await API.getFavorites();
        const data = response.data || {};
        const next = emptyFavoriteIds();
        for (const group of FAVORITE_GROUP_CODES) {
          const ids = data[group];
          if (Array.isArray(ids)) {
            next[group] = new Set(ids);
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
    async toggle(group, pk) {
      const set = this.favoriteIds[group];
      if (!set) {
        console.error(`Unknown favorite group ${group}`);
        return;
      }
      /*
       * Optimistic flip: mutate locally, fire the matching API call,
       * and roll back if the server rejects so the UI never lies.
       */
      const wasFavorite = set.has(pk);
      this._setLocal(group, pk, !wasFavorite);
      const apiCall = wasFavorite ? API.removeFavorite : API.addFavorite;
      try {
        await apiCall(group, pk);
      } catch (error) {
        this._setLocal(group, pk, wasFavorite);
        console.error(error);
      }
    },
    _setLocal(group, pk, on) {
      const set = this.favoriteIds[group];
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
