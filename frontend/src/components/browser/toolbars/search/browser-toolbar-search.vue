<template>
  <v-slide-y-transition>
    <v-toolbar v-if="isSearchOpen" density="compact" :height="toolbarHeight">
      <v-toolbar-items id="searchToolbarItems">
        <BrowserSearchCombobox />
        <SearchHelp />
      </v-toolbar-items>
    </v-toolbar>
  </v-slide-y-transition>
</template>

<script>
import { mapState } from "pinia";

import BrowserSearchCombobox from "@/components/browser/toolbars/search/search-combobox.vue";
import SearchHelp from "@/components/browser/toolbars/search/search-help.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSearchToolbar",
  components: {
    BrowserSearchCombobox,
    SearchHelp,
  },
  computed: {
    ...mapState(useBrowserStore, {
      isSearchOpen: (state) => state.isSearchOpen,
      toolbarHeight: (state) => 64 + 12 * Boolean(state.page.searchError),
    }),
  },
};
</script>

<style scoped lang="scss">
#searchToolbarItems {
  width: 100%;
}
</style>
