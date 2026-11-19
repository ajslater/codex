/*
 * Reading lists: the admin table and its dialogs, and a user's own lists
 * for the Add to list menus.
 */
import { defineStore } from "pinia";

import * as API from "@/api/v4/reading-lists";
import READING_LIST_CHOICES from "@/choices/reading-list-choices.json";
import router from "@/plugins/router";
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

// Reading list actions happen outside forms: they report as notices.
function reportError(error) {
  useCommonStore().setErrorNotice(error);
}

export const useReadingListsStore = defineStore("readingLists", {
  state: () => ({
    lists: [],
    listsLoaded: false,
    errorCount: 0,
    errors: [],
    suggestions: [],
    mappings: [],
    myLists: [],
    myListsLoaded: false,
  }),
  getters: {
    listsByPk(state) {
      return Object.fromEntries(state.lists.map((list) => [list.pk, list]));
    },
  },
  actions: {
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
        await API.listAction(pk, action);
        useCommonStore().setNotice(`Queued: ${action}.`);
      } catch (error) {
        reportError(error);
      }
    },
    async bulk(action, pks) {
      try {
        await API.bulkAction(action, pks);
        useCommonStore().setNotice(`Queued: ${action} for ${pks.length}.`);
        if (action === "delete") await this.loadLists();
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
      try {
        const response = await API.getMyLists();
        this.myLists = response.data.lists || [];
        this.myListsLoaded = true;
      } catch (error) {
        reportError(error);
      }
    },
    async addToList(pk, comics) {
      try {
        const response = await API.addEntries(pk, comics);
        const added = response.data.added || 0;
        useCommonStore().setNotice(
          `Added ${added} comic${added === 1 ? "" : "s"} to the list.`,
        );
        await this.loadMyLists();
      } catch (error) {
        reportError(error);
      }
    },
    async removeFromList(pk, comics) {
      // Hand-added comics go; any other is hidden, as its source would
      // bring it back. Returns whether anything changed.
      try {
        const response = await API.removeComics(pk, comics);
        const { removed = 0, hidden = 0 } = response.data || {};
        const parts = [];
        if (removed) parts.push(`Removed ${countComics(removed)}`);
        if (hidden) parts.push(`hid ${countComics(hidden)} its sources hold`);
        const text =
          parts.length > 0
            ? `${parts.join(", ")} from the list.`
            : "Those comics were not in the list.";
        useCommonStore().setNotice(
          text.charAt(0).toUpperCase() + text.slice(1),
        );
        return Boolean(removed || hidden);
      } catch (error) {
        reportError(error);
        return false;
      }
    },
    async addTargets(pk, targets) {
      try {
        const response = await API.addTargets(pk, targets);
        const { added = 0, name = "" } = response.data || {};
        useCommonStore().setNotice(
          `Added ${added} comic${added === 1 ? "" : "s"} to ${name}.`,
        );
        await this.loadMyLists();
        return added;
      } catch (error) {
        reportError(error);
      }
    },
    async createList(name, comics = []) {
      try {
        const response = await API.createList(name, comics);
        await this.loadMyLists();
        return response.data;
      } catch (error) {
        reportError(error);
      }
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
        await this.loadMyLists();
      } catch (error) {
        reportError(error);
      }
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
