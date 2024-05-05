<template>
  <v-slide-y-transition>
    <v-toolbar v-if="isQuery || isSearchOpen" density="compact" :height="64">
      <v-toolbar-items id="searchToolbarItems">
        <BrowserSearchCombobox />
      </v-toolbar-items>
    </v-toolbar>
  </v-slide-y-transition>
</template>

<script>
import { mapState } from "pinia";

import BrowserSearchCombobox from "@/components/browser/toolbars/top/search-combobox.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSearchToolbar",
  components: {
    BrowserSearchCombobox,
  },
  computed: {
    ...mapState(useBrowserStore, {
      isSearchOpen: (state) => state.isSearchOpen,
      isQuery: (state) => Boolean(state.settings.q),
    }),
  },
};
</script>

<style scoped lang="scss">
#searchToolbarItems {
  width: 100%;
}
</style>
