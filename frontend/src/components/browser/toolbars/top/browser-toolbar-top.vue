<template>
  <v-toolbar id="browserToolbarTop" flat density="compact" :height="48">
    <v-toolbar-items id="browserToolbarLeftItems">
      <BrowserTopGroupSelect />
      <BrowserFilterBySelect />
      <BrowserOrderBySelect v-if="!isTableMode" />
      <BrowserOrderReverseButton v-if="!isTableMode" />
      <BrowserSearchButton />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items>
      <BrowserColumnsButton />
      <BrowserViewModeToggle />
      <SettingsDrawerButton />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiFamilyTree, mdiMagnify } from "@mdi/js";
import { mapState } from "pinia";

import BrowserColumnsButton from "@/components/browser/toolbars/top/columns-button.vue";
import BrowserFilterBySelect from "@/components/browser/toolbars/top/filter-by-select.vue";
import BrowserOrderBySelect from "@/components/browser/toolbars/top/order-by-select.vue";
import BrowserOrderReverseButton from "@/components/browser/toolbars/top/order-reverse-button.vue";
import BrowserSearchButton from "@/components/browser/toolbars/top/search-button.vue";
import BrowserTopGroupSelect from "@/components/browser/toolbars/top/top-group-select.vue";
import BrowserViewModeToggle from "@/components/browser/toolbars/top/view-mode-toggle.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserTopToolbar",
  components: {
    BrowserColumnsButton,
    BrowserFilterBySelect,
    BrowserSearchButton,
    BrowserTopGroupSelect,
    BrowserOrderBySelect,
    BrowserOrderReverseButton,
    BrowserViewModeToggle,
    SettingsDrawerButton,
  },
  data() {
    return {
      mdiMagnify,
      mdiFamilyTree,
      browseMode: "filter",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      /*
       * Table view replaces the dropdown + reverse-button with
       * header-click sorting; hide them in that mode.
       */
      isTableMode: (state) => state.settings.viewMode === "table",
    }),
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
@use "sass:map";

#browserToolbarTop {
  padding-top: calc(5px + env(safe-area-inset-top));
  padding-bottom: 5px;
  padding-left: max(18px, calc(env(safe-area-inset-left) / 2));
  padding-right: 0px; // given to the settings drawer button
}

@media #{map.get(vuetify.$display-breakpoints, 'xs')} {
  #browserToolbarTop {
    padding-top: env(safe-area-inset-top);
    padding-left: max(10px, calc(env(safe-area-inset-left) / 2));
  }
}
</style>
