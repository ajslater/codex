/*
 * Reading lists: the admin table and its dialogs, and a user's own lists
 * for the Add to list menus.
 */
import { defineStore } from "pinia";

import * as API from "@/api/v4/reading-lists";
import { useCommonStore } from "@/stores/common";

export const SOURCE_KINDS = Object.freeze({
  tags: "File Tags",
  upload: "Upload",
  url: "URL",
  catalog: "DieselTech Catalog",
  metron_list: "Metron Reading List",
  metron_arc: "Metron Story Arc",
  comicvine_arc: "Comic Vine Story Arc",
});

export const EXPORT_FORMATS = Object.freeze([
  { value: "cbl", title: "ComicRack CBL" },
  { value: "json-cbl", title: "json-cbl" },
]);

function reportError(error) {
  useCommonStore().setErrors(error);
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
        useCommonStore().setSuccess(`Queued: ${action}.`);
      } catch (error) {
        reportError(error);
      }
    },
    async bulk(action, pks) {
      try {
        await API.bulkAction(action, pks);
        useCommonStore().setSuccess(`Queued: ${action} for ${pks.length}.`);
        if (action === "delete") await this.loadLists();
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
        useCommonStore().setSuccess(
          `Added ${added} comic${added === 1 ? "" : "s"} to the list.`,
        );
        await this.loadMyLists();
      } catch (error) {
        reportError(error);
      }
    },
    async addTargets(pk, targets) {
      try {
        const response = await API.addTargets(pk, targets);
        const { added = 0, name = "" } = response.data || {};
        useCommonStore().setSuccess(
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
        await this.loadMyLists();
        return response.data;
      } catch (error) {
        reportError(error);
      }
    },
  },
});
