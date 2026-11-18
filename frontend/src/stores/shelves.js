import { defineStore } from "pinia";
import { markRaw } from "vue";

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

// Run ``next`` once ``ahead`` is done. A membership change never rejects.
async function after(ahead, next) {
  await ahead;
  return next();
}

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

// Drop a shelf's queue entry once its last change is done.
async function forgetWhenDone(pending, shelfPk, change) {
  await change;
  if (pending.get(shelfPk) === change) {
    pending.delete(shelfPk);
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
    // The user the shelves belong to.
    userId: undefined,
    /*
     * Bumped after the server accepts a membership change. Views that show
     * server-computed shelf lists (the table's Shelves column, the metadata
     * dialog) watch it and refetch: effective membership runs through
     * parents, so it can't be patched locally.
     */
    membershipVersion: 0,
    /*
     * The last membership change queued for each shelf, by shelf pk, so
     * overlapping changes to one shelf reach the server in the order they
     * were made. Raw: promises that nothing renders.
     */
    pendingChanges: markRaw(new Map()),
  }),
  getters: {
    /*
     * Curried, like the favorites getter this replaces, so a caller's
     * computed tracks only the Sets it probes.
     */
    isShelved: (state) => (collection, pk) =>
      state.shelves.some((shelf) => shelf.items[collection]?.has(pk)),
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
    /*
     * The store's shelves for server-sent shelf pks, in name order. Unknown
     * pks (a shelf deleted since the response) drop out.
     */
    shelvesByPks: (state) => (pks) => {
      if (!Array.isArray(pks) || pks.length === 0) return [];
      const wanted = new Set(pks);
      return state.shelves.filter((shelf) => wanted.has(shelf.pk));
    },
    shelfNames: (state) => state.shelves.map((shelf) => shelf.name),
  },
  actions: {
    async hydrate(userId) {
      // Another user's shelves go first, so they never show for this one.
      if (userId !== this.userId) {
        this.clear();
        this.userId = userId;
      }
      try {
        const response = await API.getShelves();
        // A response for a user who has since gone is dropped.
        if (userId !== this.userId) return;
        const shelves = (response.data?.shelves || []).map((shelf) =>
          toShelf(shelf),
        );
        shelves.sort(byName);
        this.shelves = shelves;
      } catch (error) {
        console.error(error);
      }
    },
    async createShelf(name) {
      /*
       * Resolves to the new shelf, and rejects when the server refuses, so
       * the caller can show why: the name is taken or too long.
       */
      const response = await API.createShelf(name);
      const shelf = toShelf(response.data);
      this.shelves = [...this.shelves, shelf].sort(byName);
      // Hand back the reactive copy so callers can mutate membership.
      return this.shelves.find((s) => s.pk === shelf.pk);
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
    setTargetsMembership(shelfPk, targets, on) {
      /*
       * One change per shelf at a time: overlapping changes sent together
       * could land in either order and leave the server opposite to the
       * store. A change with none ahead of it starts at once, so its flip
       * stays immediate.
       */
      const pending = this.pendingChanges;
      const ahead = pending.get(shelfPk);
      const run = () => this._changeMembership(shelfPk, targets, on);
      const change = ahead ? after(ahead, run) : run();
      pending.set(shelfPk, change);
      void forgetWhenDone(pending, shelfPk, change);
      return change;
    },
    async _changeMembership(shelfPk, targets, on) {
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
        await API.updateShelfItems(shelfPk, {
          [on ? "add" : "remove"]: changed,
        });
        this.membershipVersion += 1;
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
      this.$patch({ shelves: [], userId: undefined });
    },
  },
});
