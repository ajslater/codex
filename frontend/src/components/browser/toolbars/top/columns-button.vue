<template>
  <div v-if="isTableMode">
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
      isTableMode: (state) => state.settings.viewMode === "table",
    }),
  },
};
</script>
