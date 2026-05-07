<template>
  <ToolbarButton
    class="viewModeToggle"
    icon
    :title="title"
    @click="toggleViewMode"
  >
    <v-icon>{{ icon }}</v-icon>
  </ToolbarButton>
</template>

<script>
import { mdiTable, mdiViewGrid } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import BROWSER_CHOICES from "@/choices/browser-choices.json";
import ToolbarButton from "@/components/browser/toolbars/top/toolbar-button.vue";
import { useBrowserStore } from "@/stores/browser";

const _COVER_FALLBACK_ORDER_KEY = "sort_name";

export default {
  name: "BrowserViewModeToggle",
  components: {
    ToolbarButton,
  },
  computed: {
    ...mapState(useBrowserStore, {
      viewMode: (state) => state.settings.viewMode,
      orderBy: (state) => state.settings.orderBy,
      orderReverse: (state) => state.settings.orderReverse,
      orderExtraKeys: (state) => state.settings.orderExtraKeys ?? [],
    }),
    isTable() {
      return this.viewMode === "table";
    },
    icon() {
      // Show the icon for the *other* mode — clicking it switches to that mode.
      return this.isTable ? mdiViewGrid : mdiTable;
    },
    title() {
      return this.isTable ? "switch to cover view" : "switch to table view";
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    /*
     * When transitioning into cover mode, the cover-view's order-by
     * dropdown only surfaces a curated subset of keys
     * (``BROWSER_COVER_ORDER_BY_KEYS``). If the current primary
     * isn't in that subset (because the user shift-clicked their
     * way to a multi-column sort using table-only keys), the
     * dropdown shows a blank / unrecognizable value. Normalize on
     * the transition: walk ``[orderBy, ...orderExtraKeys]`` in
     * priority order and promote the first cover-friendly entry
     * to primary, removing it from the extras list. If nothing
     * matches, fall back to ``sort_name``. The remaining extras
     * stay around — they're inert in cover mode but flip back when
     * the user returns to table view.
     */
    _coverOrderPatch() {
      const coverKeys = new Set(BROWSER_CHOICES.COVER_ORDER_BY_KEYS);
      if (coverKeys.has(this.orderBy)) return null;
      const extras = this.orderExtraKeys;
      const promoted = extras.find((entry) => coverKeys.has(entry.key));
      if (!promoted) {
        return {
          orderBy: _COVER_FALLBACK_ORDER_KEY,
          orderReverse: false,
          orderExtraKeys: extras,
        };
      }
      return {
        orderBy: promoted.key,
        orderReverse: Boolean(promoted.reverse),
        orderExtraKeys: extras.filter((entry) => entry.key !== promoted.key),
      };
    },
    toggleViewMode() {
      const switchingToCover = this.isTable;
      const patch = { viewMode: switchingToCover ? "cover" : "table" };
      if (switchingToCover) {
        Object.assign(patch, this._coverOrderPatch() ?? {});
      }
      this.setSettings(patch);
    },
  },
};
</script>
