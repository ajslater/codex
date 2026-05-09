<template>
  <!--
    Multi-root template so the ToolbarButton sits as a *direct*
    child of the parent ``<v-toolbar-items>`` flex container.
    Wrapping it in a ``<div>`` breaks the toolbar's flex-item
    sizing so v-btn falls back to its default "icon" shape (the
    rounded oval the user noticed). The dialog is a teleported
    portal so its sibling position is irrelevant; we mount it
    unconditionally so dialog state survives short button-hidden
    intervals (e.g., a viewport resize between table and cover).
   -->
  <ToolbarButton
    v-if="showButton"
    class="columnsButton"
    :icon="mdiViewColumnOutline"
    title="choose columns"
    @click="dialogOpen = true"
  />
  <BrowserTableColumnPicker v-model="dialogOpen" />
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
