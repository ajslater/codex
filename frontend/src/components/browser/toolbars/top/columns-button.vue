<template>
  <div v-if="showButton">
    <ToolbarButton
      class="columnsButton"
      icon
      title="choose columns"
      @click="dialogOpen = true"
    >
      <v-icon>{{ mdiViewColumnOutline }}</v-icon>
    </ToolbarButton>
    <BrowserTableColumnPicker v-model="dialogOpen" />
  </div>
</template>

<script>
import { mdiViewColumnOutline } from "@mdi/js";
import { mapState } from "pinia";

import BrowserTableColumnPicker from "@/components/browser/table/browser-table-column-picker.vue";
import ToolbarButton from "@/components/browser/toolbars/top/toolbar-button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserColumnsButton",
  components: {
    ToolbarButton,
    BrowserTableColumnPicker,
  },
  data() {
    return {
      mdiViewColumnOutline,
      dialogOpen: false,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      tableModeRequested: (state) => state.settings.viewMode === "table",
    }),
    showButton() {
      /*
       * The picker is only meaningful when the table is actually
       * rendering. Hide it when the user has table mode set but is
       * on a viewport too narrow for the table (mobile auto-fallback)
       * — the cover grid wins, and column choices don't apply.
       */
      return this.tableModeRequested && !this.$vuetify.display.smAndDown;
    },
  },
};
</script>
