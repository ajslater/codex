import { defineStore } from "pinia";

import * as API from "@/api/v3/browser";
import { getTimestamp } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

const _itemKey = (item) => {
  return `${item.group}:${item.ids.join(",")}`;
};

const _groupSelectedItems = (selectedItems) => {
  // Group selected items by their group field.
  const grouped = {};
  for (const item of selectedItems.values()) {
    if (!grouped[item.group]) {
      grouped[item.group] = [];
    }
    grouped[item.group].push(item);
  }
  return grouped;
};

const _collectPks = (items) => {
  // Collect all unique pks from a list of items.
  const pks = new Set();
  for (const item of items) {
    for (const pk of item.ids) {
      pks.add(pk);
    }
  }
  return [...pks].sort((a, b) => a - b);
};

export const useBrowserSelectManyStore = defineStore("browserSelectMany", {
  state: () => ({
    active: false,
    selectedItems: new Map(),
  }),
  getters: {
    selectedCount(state) {
      return state.selectedItems.size;
    },
    isSelected(state) {
      return (item) => state.selectedItems.has(_itemKey(item));
    },
    hasSelection(state) {
      return state.selectedItems.size > 0;
    },
    /**
     * Build a composite item suitable for the metadata dialog.
     * Combines all selected items into one object with merged ids.
     */
    compositeItem(state) {
      if (state.selectedItems.size === 0) {
        return null;
      }
      const grouped = _groupSelectedItems(state.selectedItems);
      const groups = Object.keys(grouped);
      // Use the first group type found.
      const group = groups[0];
      const items = grouped[group];
      const pks = _collectPks(items);
      const names = items.map((item) => item.name).filter(Boolean);
      const childCount = items.reduce(
        (sum, item) => sum + (item.childCount || 1),
        0,
      );
      return {
        group,
        ids: pks,
        pks,
        name: names.length > 1 ? `${names.length} items` : names[0] || "",
        childCount,
        finished: null,
      };
    },
  },
  actions: {
    deactivate() {
      this.active = false;
      this.selectedItems = new Map();
    },
    toggleItem(item) {
      if (!this.active) {
        this.active = true;
      }
      const key = _itemKey(item);
      if (this.selectedItems.has(key)) {
        this.selectedItems.delete(key);
      } else {
        this.selectedItems.set(key, item);
      }
      // Trigger reactivity by replacing the map.
      this.selectedItems = new Map(this.selectedItems);
      // Deactivate if nothing selected.
      if (this.selectedItems.size === 0) {
        this.active = false;
      }
    },
    selectAll() {
      this.active = true;
      const browserStore = useBrowserStore();
      const cards = [
        ...(browserStore.page.groups ?? []),
        ...(browserStore.page.books ?? []),
      ];
      for (const item of cards) {
        const key = _itemKey(item);
        this.selectedItems.set(key, item);
      }
      this.selectedItems = new Map(this.selectedItems);
    },
    clearSelection() {
      this.selectedItems = new Map();
      this.active = false;
    },
    async markFinished(finished) {
      const browserStore = useBrowserStore();
      if (!browserStore.isAuthorized || this.selectedItems.size === 0) {
        return;
      }
      const grouped = _groupSelectedItems(this.selectedItems);
      const promises = [];
      for (const [group, items] of Object.entries(grouped)) {
        const pks = _collectPks(items);
        const params = { group, ids: pks };
        promises.push(
          API.updateGroupBookmarks(params, browserStore.filterOnlySettings, {
            finished,
          }),
        );
      }
      await Promise.all(promises);
      browserStore.loadBrowserPage(getTimestamp());
    },
    download() {
      const browserStore = useBrowserStore();
      if (this.selectedItems.size === 0) {
        return;
      }
      const grouped = _groupSelectedItems(this.selectedItems);
      for (const [group, items] of Object.entries(grouped)) {
        const pks = _collectPks(items);
        const groupName = browserStore.groupNames[group] || "Items";
        const plural = groupName.endsWith("s") ? groupName : groupName + "s";
        const fn = `Selected ${plural}.zip`;
        const settings = browserStore.filterOnlySettings;
        const url = API.getGroupDownloadURL({ group, pks }, fn, settings, 0);
        const link = document.createElement("a");
        link.download = fn;
        link.href = url;
        link.click();
        link.remove();
      }
    },
  },
});
