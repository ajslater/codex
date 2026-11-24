/*
 * Reading lists: the admin table and its dialogs, and the lists a user may
 * change, with what each holds directly, for the list menus' toggles.
 */
import { defineStore } from "pinia";
import { markRaw } from "vue";

import * as API from "@/api/v4/reading-lists";
import READING_LIST_CHOICES from "@/choices/reading-list-choices.json";
import router from "@/plugins/router";
import { useBrowserStore } from "@/stores/browser";
import { useCommonStore } from "@/stores/common";

// Source kind -> label, from the backend's ReadingListSourceKind.
export const SOURCE_KINDS = Object.freeze(
  Object.fromEntries(
    READING_LIST_CHOICES.sourceKinds.map(({ value, title }) => [value, title]),
  ),
);

// List type -> label: "story" is a Story Arc. Others show as given.
const LIST_TYPES = Object.freeze(
  Object.fromEntries(
    READING_LIST_CHOICES.listTypes.map(({ value, title }) => [value, title]),
  ),
);

export function listTypeLabel(listType) {
  return listType ? LIST_TYPES[listType] || listType.replaceAll("-", " ") : "";
}

// json-cbl, the newer JSON standard, first; then the classic XML.
export const EXPORT_FORMATS = Object.freeze([
  { value: "json-cbl", title: "json-cbl" },
  { value: "cbl", title: "ComicRack CBL" },
]);

function countComics(count) {
  return `${count} comic${count === 1 ? "" : "s"}`;
}

function countLists(count) {
  return `${count} reading list${count === 1 ? "" : "s"}`;
}

function countSources(count) {
  return `${count} source${count === 1 ? "" : "s"}`;
}

/*
 * Say what a list action did, from what the server answered, instead of
 * naming the action. When nothing qualified, say why.
 */
const ACTION_NOTICES = Object.freeze({
  refresh: ({ queued = 0 }) =>
    queued
      ? `Fetching ${countSources(queued)} again. A list changes if its source did.`
      : "Nothing to fetch again: uploads and lists from tags have no remote source.",
  complete: ({ queued = 0 }) =>
    queued
      ? `Fetching the whole story arc of ${countLists(queued)} from Metron or Comic Vine.`
      : "Nothing to complete: a list needs story arc tags that carry a Metron or Comic Vine arc id.",
  rematch: ({ queued = 0 }) =>
    `Matching the missing issues of ${countLists(queued)} again.`,
  recombine: ({ queued = 0 }) =>
    `Recomputing ${countLists(queued)} from their sources.`,
  write: ({ queued = 0, skipped = 0 }) => {
    if (!queued) {
      return "Nothing to write: only global lists with comics in writable libraries are written.";
    }
    const verb = skipped === 1 ? "is" : "are";
    const skip = skipped
      ? ` ${countComics(skipped)} in read-only libraries ${verb} skipped.`
      : "";
    return `Writing the story arc into ${countComics(queued)}.${skip}`;
  },
  copy_global: ({ copied = 0 }) =>
    copied
      ? `Copied ${countLists(copied)} to global lists.`
      : "Already global lists: nothing to copy.",
  delete: ({ deleted = 0 }) => `Deleted ${countLists(deleted)}.`,
});

export function actionNotice(action, data) {
  const notice = ACTION_NOTICES[action];
  return notice ? notice(data || {}) : "Done.";
}

// Reading list actions happen outside forms: they report as notices.
function reportError(error) {
  useCommonStore().setErrorNotice(error);
}

// What a list holds directly: issues by hand, and whole collections.
export const LIST_ITEM_COLLECTIONS = Object.freeze([
  "publishers",
  "imprints",
  "series",
  "volumes",
  "folders",
  "arcs",
  "comics",
]);
const COMICS = "comics";

// Run ``next`` once ``ahead`` is done. A membership change never rejects.
async function after(ahead, next) {
  await ahead;
  return next();
}

function eachTarget(targets, visit) {
  // Walk a ``{collection: [pks]}`` map, skipping unknown collections.
  const entries = Object.entries(targets || {});
  for (const [collection, pks] of entries) {
    if (!LIST_ITEM_COLLECTIONS.includes(collection)) {
      console.error(`Unknown list collection ${collection}`);
      continue;
    }
    const targetPks = pks || [];
    for (const pk of targetPks) {
      visit(collection, pk);
    }
  }
}

// Drop a list's queue entry once its last change is done.
async function forgetWhenDone(pending, listPk, change) {
  await change;
  if (pending.get(listPk) === change) {
    pending.delete(listPk);
  }
}

function joinNames(names) {
  return names.length < 2
    ? names.join("")
    : `${names.slice(0, -1).join(", ")} and ${names.at(-1)}`;
}

function membershipCounts(list, targets) {
  let total = 0;
  let on = 0;
  eachTarget(targets, (collection, pk) => {
    total += 1;
    if (list.items[collection].has(pk)) on += 1;
  });
  return { total, on };
}

function removedText(removed, hidden) {
  const parts = [];
  if (removed) parts.push(`Removed ${countComics(removed)}`);
  if (hidden) parts.push(`hid ${countComics(hidden)} its sources hold`);
  if (parts.length === 0) return "";
  const text = `${parts.join(", ")} from the list.`;
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function setLocal(set, pk, on) {
  if (on) {
    set.add(pk);
  } else {
    set.delete(pk);
  }
}

/*
 * The items that refused comics come in through, once each. A comic a
 * series delivers can't be taken out on its own: the series goes instead.
 */
function throughItems(refused) {
  const seen = new Set();
  const items = [];
  const rows = refused || [];
  for (const { item } of rows) {
    if (!item?.pk || seen.has(item.pk)) {
      continue;
    }

    seen.add(item.pk);
    items.push(item);
  }
  return items;
}

function toMyList(list) {
  // API list -> store list: each collection's ids become a Set.
  const items = {};
  for (const collection of LIST_ITEM_COLLECTIONS) {
    const ids = list.items?.[collection];
    items[collection] = new Set(Array.isArray(ids) ? ids : []);
  }
  return { ...list, items };
}

export const useReadingListsStore = defineStore("readingLists", {
  state: () => ({
    lists: [],
    listsLoaded: false,
    errorCount: 0,
    errors: [],
    suggestions: [],
    mappings: [],
    /*
     * ``[{pk, name, personal, count, editable, items: {collection:
     * Set<pk>}}]``: the user's own lists, then for an admin the global
     * ones, each with what it holds directly.
     */
    myLists: [],
    myListsLoaded: false,
    // The user the lists belong to.
    myListsUserId: undefined,
    /*
     * Bumped after the server accepts a membership change. Views that show
     * server-computed list names (the table's Reading Lists column, the
     * metadata dialog) watch it and refetch: a comic is in a list through
     * its series too, so it can't be patched locally.
     */
    membershipVersion: 0,
    /*
     * The last membership change queued for each list, by list pk, so
     * overlapping changes to one list reach the server in the order they
     * were made. Raw: promises that nothing renders.
     */
    pendingChanges: markRaw(new Map()),
  }),
  getters: {
    listsByPk(state) {
      return Object.fromEntries(state.lists.map((list) => [list.pk, list]));
    },
    editableLists: (state) => state.myLists.filter((list) => list.editable),
    // The user's own list names: a new one must not repeat them.
    myListNames: (state) =>
      state.myLists.filter((list) => list.personal).map((list) => list.name),
    /*
     * "all" | "some" | "none" of the ``{collection: [pks]}`` targets are
     * in the list directly. Drives the menu's checked / mixed checkbox.
     */
    membershipState: (state) => (listPk, targets) => {
      const list = state.myLists.find((row) => row.pk === listPk);
      if (!list) return "none";
      const { total, on } = membershipCounts(list, targets);
      if (!total || !on) return "none";
      return on === total ? "all" : "some";
    },
    // True when every target is directly in at least one list.
    isEveryListed: (state) => (targets) => {
      let total = 0;
      let listed = 0;
      eachTarget(targets, (collection, pk) => {
        total += 1;
        if (state.myLists.some((list) => list.items[collection].has(pk))) {
          listed += 1;
        }
      });
      return total > 0 && listed === total;
    },
  },
  actions: {
    clear() {
      // On logout: the next account must not see this one's lists.
      this.$patch({
        myLists: [],
        myListsLoaded: false,
        myListsUserId: undefined,
      });
    },
    async hydrate(userId) {
      // Another user's lists go first, so they never show for this one.
      if (userId !== this.myListsUserId) {
        this.clear();
        this.myListsUserId = userId;
      }
      await this.loadMyLists();
    },
    async continueReading(pk) {
      // Open the first issue of the list not yet finished, in list order.
      try {
        const response = await API.getContinue(pk);
        const next = response.data?.continue;
        if (!next) {
          useCommonStore().setNotice("You have read every issue of this list.");
          return;
        }
        await router.push({
          name: "reader",
          params: { pk: next.pk },
          query: { page: next.page || 0, list: pk },
        });
      } catch (error) {
        reportError(error);
      }
    },
    async loadLists() {
      try {
        const response = await API.getAdminLists();
        this.lists = response.data.lists || [];
        this.errorCount = response.data.errorCount || 0;
        this.listsLoaded = true;
      } catch (error) {
        reportError(error);
      }
    },
    async loadSuggestions() {
      try {
        const response = await API.getSuggestions();
        this.suggestions = response.data.suggestions || [];
      } catch (error) {
        reportError(error);
      }
    },
    async loadErrors() {
      try {
        const response = await API.getErrors();
        this.errors = Array.isArray(response.data) ? response.data : [];
      } catch (error) {
        reportError(error);
      }
    },
    async clearErrors() {
      await API.clearErrors();
      this.errors = [];
      this.errorCount = 0;
    },
    async loadTable() {
      // The admin table and the suggestions drawn from it, together.
      await Promise.all([this.loadLists(), this.loadSuggestions()]);
    },
    async updateDetails(pk, details) {
      try {
        await API.updateAdminList(pk, details);
        useCommonStore().setNotice("Saved the list's details.");
        await this.loadTable();
        return true;
      } catch (error) {
        reportError(error);
        return false;
      }
    },
    async deleteMapping(pk) {
      try {
        await API.deleteMapping(pk);
        useCommonStore().setNotice(
          "Forgot the series mapping. Issues it matched keep their comics.",
        );
        await this.loadMappings();
      } catch (error) {
        reportError(error);
      }
    },
    async loadMappings() {
      try {
        const response = await API.getMappings();
        this.mappings = response.data.mappings || [];
      } catch (error) {
        reportError(error);
      }
    },
    async act(pk, action) {
      try {
        const response = await API.listAction(pk, action);
        useCommonStore().setNotice(actionNotice(action, response?.data));
        if (action === "delete") await this.loadTable();
      } catch (error) {
        reportError(error);
      }
    },
    async bulk(action, pks) {
      try {
        const response = await API.bulkAction(action, pks);
        useCommonStore().setNotice(actionNotice(action, response?.data));
        if (action === "delete" || action === "copy_global") {
          await this.loadTable();
        }
      } catch (error) {
        reportError(error);
      }
    },
    async copyToGlobal(pk) {
      try {
        const response = await API.listAction(pk, "copy_global");
        const copied = response.data?.copied || 0;
        useCommonStore().setNotice(
          copied
            ? "Copied to a new global reading list."
            : "Already a global list: nothing to copy.",
        );
        await this.loadLists();
      } catch (error) {
        reportError(error);
      }
    },
    async setPrivate(pk, isPrivate) {
      try {
        await API.updateAdminList(pk, { private: isPrivate });
        await this.loadLists();
      } catch (error) {
        reportError(error);
      }
    },
    async loadMyLists() {
      const userId = this.myListsUserId;
      try {
        const response = await API.getMyLists();
        // A response for a user who has since gone is dropped.
        if (userId !== this.myListsUserId) return;
        this.myLists = (response.data.lists || []).map((list) =>
          toMyList(list),
        );
        this.myListsLoaded = true;
      } catch (error) {
        reportError(error);
      }
    },
    setTargetsMembership(listPk, targets, on) {
      /*
       * One change per list at a time: overlapping changes sent together
       * could land in either order and leave the server opposite to the
       * store. A change with none ahead of it starts at once, so its flip
       * stays immediate.
       */
      const pending = this.pendingChanges;
      const ahead = pending.get(listPk);
      const run = () => this._changeMembership(listPk, targets, on);
      const change = ahead ? after(ahead, run) : run();
      pending.set(listPk, change);
      void forgetWhenDone(pending, listPk, change);
      return change;
    },
    async _changeMembership(listPk, targets, on) {
      /*
       * Drive every ``{collection: [pks]}`` target into (or out of) one
       * list with a single PATCH. Optimistic: flip locally first, then
       * roll back what was flipped if the server rejects it, or the one
       * target it refused, so the menu never lies. Targets already in the
       * wanted state are skipped, and nothing is sent when nothing changes.
       */
      const list = this.myLists.find((row) => row.pk === listPk);
      if (!list) {
        console.error(`Unknown reading list ${listPk}`);
        return false;
      }
      const changed = {};
      eachTarget(targets, (collection, pk) => {
        const set = list.items[collection];
        if (set.has(pk) === on) return;
        setLocal(set, pk, on);
        changed[collection] ??= [];
        changed[collection].push(pk);
      });
      if (Object.keys(changed).length === 0) return true;
      try {
        const response = await API.updateItems(listPk, {
          [on ? "add" : "remove"]: changed,
        });
        const data = response?.data || {};
        this._undoRefused(list, data.refused, on);
        if (Number.isSafeInteger(data.count)) list.count = data.count;
        this.membershipVersion += 1;
        return true;
      } catch (error) {
        for (const [collection, pks] of Object.entries(changed)) {
          for (const pk of pks) {
            setLocal(list.items[collection], pk, !on);
          }
        }
        reportError(error);
        return false;
      }
    },
    _undoRefused(list, refused, on) {
      // Put back what the server would not change, and say why.
      const reasons = [];
      const rows = refused || [];
      for (const row of rows) {
        const collection = row.collection || COMICS;
        const pk = row.pk ?? row.comic;
        if (Object.hasOwn(list.items, collection)) {
          setLocal(list.items[collection], pk, !on);
        }
        const reason =
          row.reason ||
          (row.item ? `It is there through ${row.item.label}.` : "");
        if (reason && !reasons.includes(reason)) reasons.push(reason);
      }
      if (reasons.length > 0) {
        useCommonStore().setNotice(reasons.join(" "), { error: true });
      }
    },
    _noteCount(pk, count) {
      const list = this.myLists.find((row) => row.pk === pk);
      if (list && Number.isSafeInteger(count)) list.count = count;
    },
    async removeFromList(pk, comics) {
      /*
       * Hand-added comics go; any other is hidden, as its source would
       * bring it back. A comic a series, folder or other item delivers
       * can't go on its own: the notice offers to remove that item.
       * Returns whether anything changed.
       */
      try {
        const response = await API.updateItems(pk, { remove: { comics } });
        const {
          removed = 0,
          hidden = 0,
          refused = [],
          count,
        } = response.data || {};
        this._noteCount(pk, count);
        if (removed || hidden) this.membershipVersion += 1;
        const text = removedText(removed, hidden);
        if (throughItems(refused).length > 0) {
          this._offerItemRemoval(pk, refused, text);
        } else {
          useCommonStore().setNotice(
            text || "Those comics were not in the list.",
          );
        }
        return Boolean(removed || hidden);
      } catch (error) {
        reportError(error);
        return false;
      }
    },
    _offerItemRemoval(pk, refused, removed) {
      const items = throughItems(refused);
      const names = joinNames(items.map((item) => item.label));
      const subject =
        refused.length === 1
          ? "That issue is"
          : `${refused.length} of those issues are`;
      const lead = removed ? `${removed} ` : "";
      const text = `${lead}${subject} in this list through ${names}.`;
      if (items.length > 1) {
        useCommonStore().setNotice(`${text} Remove those instead.`);
        return;
      }
      const [item] = items;
      useCommonStore().setNotice(text, {
        action: {
          label: `Remove ${item.label}`,
          run: () => this.removeItem(pk, item),
        },
      });
    },
    async removeItem(pk, item) {
      // Take a whole collection out of a list, with every comic it brought.
      try {
        const response = await API.updateItems(pk, {
          remove: { [item.collection]: [item.targetId] },
        });
        this._noteCount(pk, response.data?.count);
        const list = this.myLists.find((row) => row.pk === pk);
        list?.items[item.collection]?.delete(item.targetId);
        this.membershipVersion += 1;
        useCommonStore().setNotice(`Removed ${item.label} from the list.`);
        await useBrowserStore().refreshBrowserPage();
        return true;
      } catch (error) {
        reportError(error);
        return false;
      }
    },
    async createList(name) {
      /*
       * Resolves to the new list, as the store holds it, and rejects when
       * the server refuses, so the name field can say why: the name is
       * taken or too long.
       */
      const response = await API.createList(name);
      await this.loadMyLists();
      return this.myLists.find((list) => list.pk === response.data?.pk);
    },
    async renameList(pk, name) {
      try {
        await API.renameList(pk, name);
        await this.loadMyLists();
      } catch (error) {
        reportError(error);
      }
    },
    async deleteList(pk) {
      try {
        await API.deleteList(pk);
      } catch (error) {
        reportError(error);
        return false;
      }
      /*
       * A deleted list can't stay selected in the browser filter: the
       * server would match nothing and the menu has no row left to
       * untick it with.
       */
      const browserStore = useBrowserStore();
      const selected = browserStore.settings.filters?.readingLists;
      if (Array.isArray(selected) && selected.includes(pk)) {
        await browserStore.setSettings({
          filters: { readingLists: selected.filter((listPk) => listPk !== pk) },
        });
      }
      await this.loadMyLists();
      return true;
    },
    async duplicateList(pk) {
      try {
        const response = await API.duplicateList(pk);
        const copy = response.data;
        useCommonStore().setNotice(
          `Copied to your reading lists as "${copy?.name}".`,
        );
        await this.loadMyLists();
        return copy;
      } catch (error) {
        reportError(error);
      }
    },
  },
});
