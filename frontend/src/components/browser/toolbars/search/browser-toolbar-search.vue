<template>
  <v-slide-y-transition>
    <v-toolbar
      v-if="isQuery || isSearchOpen"
      id="browserToolbarSearch"
      density="compact"
      :height="64"
    >
      <v-toolbar-items id="searchToolbarItems">
        <BrowserSearchCombobox />
      </v-toolbar-items>
    </v-toolbar>
  </v-slide-y-transition>
</template>

<script>
import { mapState } from "pinia";

import BrowserSearchCombobox from "@/components/browser/toolbars/search/search-combobox.vue";
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
#browserToolbarSearch {
  padding-left: max(calc(env(safe-area-inset-left) /4) + 10px);
  padding-right: max(calc(env(safe-area-inset-right) /4) + 10px);
}
#searchToolbarItems {
  width: 100%;
}
</style>
