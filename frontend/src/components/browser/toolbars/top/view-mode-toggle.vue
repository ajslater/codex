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

import ToolbarButton from "@/components/browser/toolbars/top/toolbar-button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserViewModeToggle",
  components: {
    ToolbarButton,
  },
  computed: {
    ...mapState(useBrowserStore, {
      viewMode: (state) => state.settings.viewMode,
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
    toggleViewMode() {
      this.setSettings({ viewMode: this.isTable ? "cover" : "table" });
    },
  },
};
</script>
