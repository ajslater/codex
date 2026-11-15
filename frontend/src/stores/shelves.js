import { defineStore } from "pinia";

import * as API from "@/api/v4/shelves";
import { useBrowserStore } from "@/stores/browser";

export const SHELF_COLLECTIONS = Object.freeze([
  "publishers",
  "imprints",
  "series",
  "volumes",
  "folders",
  "arcs",
  "comics",
]);

function emptyItems() {
  const items = {};
  for (const collection of SHELF_COLLECTIONS) {
    items[collection] = new Set();
  }
  return items;
}

function toShelf({ pk, name, items }) {
  // API shelf -> store shelf: id arrays become Sets, absent ones empty.
  const sets = emptyItems();
  for (const collection of SHELF_COLLECTIONS) {
    const ids = items?.[collection];
    if (Array.isArray(ids)) {
      sets[collection] = new Set(ids);
    }
  }
  return { pk, name, items: sets };
}

const byName = (a, b) => a.name.localeCompare(b.name);

function eachTarget(targets, visit) {
  // Walk a ``{collection: [pks]}`` map, skipping unknown collections.
  const entries = Object.entries(targets || {});
  for (const [collection, pks] of entries) {
    if (!SHELF_COLLECTIONS.includes(collection)) {
      console.error(`Unknown shelf collection ${collection}`);
      continue;
    }
    const targetPks = pks || [];
    for (const pk of targetPks) {
      visit(collection, pk);
    }
  }
}

function membershipCounts(shelf, targets) {
  let total = 0;
  let on = 0;
  eachTarget(targets, (collection, pk) => {
    total += 1;
    if (shelf.items[collection].has(pk)) on += 1;
  });
  return { total, on };
}

function shelfItemCount(shelf) {
  let count = 0;
  for (const set of Object.values(shelf.items)) {
    count += set.size;
  }
  return count;
}

export const useShelvesStore = defineStore("shelves", {
  state: () => ({
    // ``[{pk, name, items: {collection: Set<pk>}}]`` ordered by name.
    shelves: [],
    hydrated: false,
  }),
  getters: {
    /*
     * Curried, like the favorites getter this replaces, so a caller's
     * computed tracks only the Sets it probes.
     */
    isShelved: (state) => (collection, pk) =>
      state.shelves.some((shelf) => shelf.items[collection]?.has(pk)),
    // The shelves holding at least one of ``pks``.
    shelvesFor: (state) => (collection, pks) =>
      state.shelves.filter((shelf) => {
        const set = shelf.items[collection];
        return Boolean(set) && pks.some((pk) => set.has(pk));
      }),
    /*
     * "all" | "some" | "none" of the ``{collection: [pks]}`` targets are
     * on the shelf. Drives the menu's checked / indeterminate checkbox.
     */
    membershipState: (state) => (shelfPk, targets) => {
      const shelf = state.shelves.find((s) => s.pk === shelfPk);
      if (!shelf) return "none";
      const { total, on } = membershipCounts(shelf, targets);
      if (!total || !on) return "none";
      return on === total ? "all" : "some";
    },
    // True when every target is on at least one shelf.
    isEveryShelved() {
      return (targets) => {
        let total = 0;
        let shelved = 0;
        eachTarget(targets, (collection, pk) => {
          total += 1;
          if (this.isShelved(collection, pk)) shelved += 1;
        });
        return total > 0 && shelved === total;
      };
    },
    // How many items a shelf holds, across every collection.
    itemCount: () => shelfItemCount,
    shelfNames: (state) => state.shelves.map((shelf) => shelf.name),
  },
  actions: {
    async hydrate() {
      try {
        const response = await API.getShelves();
        const shelves = (response.data?.shelves || []).map((shelf) =>
          toShelf(shelf),
        );
        shelves.sort(byName);
        this.$patch({ shelves, hydrated: true });
      } catch (error) {
        console.error(error);
      }
    },
    async createShelf(name) {
      // Resolves to the new shelf, or undefined when the server refuses.
      try {
        const response = await API.createShelf(name);
        const shelf = toShelf(response.data);
        this.shelves = [...this.shelves, shelf].sort(byName);
        // Hand back the reactive copy so callers can mutate membership.
        return this.shelves.find((s) => s.pk === shelf.pk);
      } catch (error) {
        console.error(error);
      }
    },
    async renameShelf(pk, name) {
      try {
        const response = await API.renameShelf(pk, name);
        const shelf = this.shelves.find((s) => s.pk === pk);
        if (!shelf) return false;
        shelf.name = response.data?.name ?? name;
        this.shelves = [...this.shelves].sort(byName);
        return true;
      } catch (error) {
        console.error(error);
        return false;
      }
    },
    async deleteShelf(pk) {
      try {
        await API.deleteShelf(pk);
      } catch (error) {
        console.error(error);
        return false;
      }
      this.shelves = this.shelves.filter((shelf) => shelf.pk !== pk);
      /*
       * A deleted shelf can't stay selected in the browser filter: the
       * server would match nothing and the menu has no row left to
       * untick it with.
       */
      const browserStore = useBrowserStore();
      const selected = browserStore.settings.filters?.shelves;
      if (Array.isArray(selected) && selected.includes(pk)) {
        await browserStore.setSettings({
          filters: { shelves: selected.filter((shelfPk) => shelfPk !== pk) },
        });
      }
      return true;
    },
    setMembership(shelfPk, collection, pks, on) {
      return this.setTargetsMembership(shelfPk, { [collection]: pks }, on);
    },
    async setTargetsMembership(shelfPk, targets, on) {
      /*
       * Drive every ``{collection: [pks]}`` target onto (or off) one
       * shelf with a single PATCH. Optimistic: flip locally first, then
       * roll back exactly what was flipped if the server rejects, so the
       * UI never lies. Targets already in the wanted state are skipped,
       * and no request is sent when nothing changes.
       */
      const shelf = this.shelves.find((s) => s.pk === shelfPk);
      if (!shelf) {
        console.error(`Unknown shelf ${shelfPk}`);
        return false;
      }
      const changed = {};
      eachTarget(targets, (collection, pk) => {
        const set = shelf.items[collection];
        if (set.has(pk) === on) return;
        this._setLocal(set, pk, on);
        changed[collection] ??= [];
        changed[collection].push(pk);
      });
      if (Object.keys(changed).length === 0) return true;
      try {
        await API.updateShelfItems(shelfPk, { [on ? "add" : "remove"]: changed });
        return true;
      } catch (error) {
        for (const [collection, pks] of Object.entries(changed)) {
          for (const pk of pks) {
            this._setLocal(shelf.items[collection], pk, !on);
          }
        }
        console.error(error);
        return false;
      }
    },
    _setLocal(set, pk, on) {
      if (on) {
        set.add(pk);
      } else {
        set.delete(pk);
      }
    },
    clear() {
      /*
       * Logout / user switch — drop the cached shelves so a different
       * user doesn't see the previous account's.
       */
      this.$patch({ shelves: [], hydrated: false });
    },
  },
});
