import { defineStore } from "pinia";

import * as API from "@/api/v4/browser";
import { getTimestamp } from "@/datetime";
import { useBrowserStore } from "@/stores/browser";

const _itemKey = (item) => {
  return `${item.collection}:${item.ids.join(",")}`;
};

const _groupSelectedItems = (selectedItems) => {
  // Group selected items by their group field.
  const grouped = {};
  for (const item of selectedItems.values()) {
    if (!grouped[item.collection]) {
      grouped[item.collection] = [];
    }
    grouped[item.collection].push(item);
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

const _visibleItems = () => {
  /*
   * Ordered list of items currently shown on the browser page.
   * Mirrors ``BrowserMain.cards`` and the table view's ``rows``:
   * table mode wins when present, otherwise spread groups + books.
   * Used by both ``selectAll`` and ``selectItemAt`` so the displayed
   * order is the single source of truth for "between" semantics.
   */
  const browserStore = useBrowserStore();
  const rows = browserStore.page.rows;
  if (Array.isArray(rows) && rows.length > 0) {
    return rows;
  }
  return [
    ...(browserStore.page.groups ?? []),
    ...(browserStore.page.books ?? []),
  ];
};

export const useBrowserSelectManyStore = defineStore("browserSelectMany", {
  state: () => ({
    active: false,
    selectedItems: new Map(),
    /*
     * The last item the user toggled or shift-extended to. Shift-click
     * uses this as the start of the range. Cleared whenever the
     * selection itself is cleared so a stale anchor from a previous
     * session never extends a new one.
     */
    lastAnchorKey: null,
  }),
  getters: {
    selectedCount(state) {
      return state.selectedItems.size;
    },
    selectedTotalChildCount(state) {
      let total = 0;
      for (const item of state.selectedItems.values()) {
        total += item.childCount || (item.collection === "comics" ? 1 : 0);
      }
      return total;
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
      this.lastAnchorKey = null;
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
        this.lastAnchorKey = null;
      } else {
        this.lastAnchorKey = key;
      }
    },
    selectItemAt(item, { shift = false } = {}) {
      /*
       * Click dispatcher for selection. Plain click → ``toggleItem``
       * (one item, anchor follows). Shift-click → fill the range from
       * the previous anchor to this item with selected = true (not a
       * toggle — matches the Gmail / Finder / VS Code convention).
       *
       * Falls back to a plain toggle when:
       *  - shift wasn't held,
       *  - there's no live anchor (first interaction of the session),
       *  - the anchor's item is no longer on the visible page (after
       *    pagination, sort change, or page reload). The anchor is
       *    invalidated implicitly by the index lookup so callers don't
       *    need to clear it on navigation.
       */
      if (!shift || !this.lastAnchorKey) {
        this.toggleItem(item);
        return;
      }
      const items = _visibleItems();
      const targetKey = _itemKey(item);
      const anchorIdx = items.findIndex(
        (i) => _itemKey(i) === this.lastAnchorKey,
      );
      const targetIdx = items.findIndex((i) => _itemKey(i) === targetKey);
      if (anchorIdx === -1 || targetIdx === -1) {
        this.toggleItem(item);
        return;
      }
      if (!this.active) {
        this.active = true;
      }
      const [lo, hi] =
        anchorIdx <= targetIdx
          ? [anchorIdx, targetIdx]
          : [targetIdx, anchorIdx];
      for (let i = lo; i <= hi; i++) {
        const member = items[i];
        this.selectedItems.set(_itemKey(member), member);
      }
      // Trigger reactivity by replacing the map.
      this.selectedItems = new Map(this.selectedItems);
      this.lastAnchorKey = targetKey;
    },
    selectAll() {
      this.active = true;
      for (const item of _visibleItems()) {
        const key = _itemKey(item);
        this.selectedItems.set(key, item);
      }
      this.selectedItems = new Map(this.selectedItems);
    },
    clearSelection() {
      this.selectedItems = new Map();
      this.active = false;
      this.lastAnchorKey = null;
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
        const params = { collection: group, ids: pks };
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
        const url = API.getGroupDownloadURL(
          { collection: group, pks },
          fn,
          settings,
          0,
        );
        const link = document.createElement("a");
        link.download = fn;
        link.href = url;
        link.click();
        link.remove();
      }
    },
    async forceUpdate() {
      const browserStore = useBrowserStore();
      if (!browserStore.isAuthorized || this.selectedItems.size === 0) {
        return;
      }
      const grouped = _groupSelectedItems(this.selectedItems);
      const promises = [];
      for (const [group, items] of Object.entries(grouped)) {
        const ids = _collectPks(items);
        promises.push(
          API.forceUpdateGroup(
            { collection: group, ids },
            browserStore.filterOnlySettings,
          ),
        );
      }
      await Promise.all(promises);
    },
  },
});
