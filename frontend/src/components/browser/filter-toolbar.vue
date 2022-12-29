<template>
  <v-toolbar
    id="browserToolbar"
    class="toolbar"
    density="compact"
    extension-height="48px"
  >
    <v-toolbar-items v-if="isCodexViewable" id="browserToolbarLeftItems">
      <BrowserTopGroupSelect id="topGroupSelect" />
      <BrowserOrderBySelect id="orderBySelect" />
      <BrowserOrderReverseButton id="orderReverseButton" />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items id="browserToolbarRightItems">
      <SettingsDrawerButton @click="isSettingsDrawerOpen = true" />
    </v-toolbar-items>
    <template #extension>
      <v-toolbar-items v-if="isCodexViewable" id="searchToolbarItems">
        <BrowserFilterBySelect id="filterSelect" />
        <BrowserSearchCombobox id="searchField" />
      </v-toolbar-items>
    </template>
  </v-toolbar>
</template>

<script>
import { mdiFamilyTree, mdiMagnify } from "@mdi/js";
import { mapGetters, mapWritableState } from "pinia";

import BrowserFilterBySelect from "@/components/browser/filter-by-select.vue";
import BrowserOrderBySelect from "@/components/browser/order-by-select.vue";
import BrowserOrderReverseButton from "@/components/browser/order-reverse-button.vue";
import BrowserSearchCombobox from "@/components/browser/search-combobox.vue";
import BrowserTopGroupSelect from "@/components/browser/top-group-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";
import { useAuthStore } from "@/stores/auth";
import { useCommonStore } from "@/stores/common";

export default {
  name: "BrowserHeader",
  components: {
    BrowserFilterBySelect,
    BrowserTopGroupSelect,
    BrowserSearchCombobox,
    BrowserOrderBySelect,
    BrowserOrderReverseButton,
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
    ...mapGetters(useAuthStore, ["isCodexViewable"]),
    ...mapWritableState(useCommonStore, ["isSettingsDrawerOpen"]),
  },
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#browserToolbar {
  padding-top: env(safe-area-inset-top);
  padding-left: calc(10px + env(safe-area-inset-left) / 4);
  padding-right: calc(10px + env(safe-area-inset-right) / 4);
}
#browserToolbarLeftItems {
  padding-top: 4px;
}
#searchToolbarItems {
  width: 100%;
}
@media #{map-get(vuetify.$display-breakpoints, 'sm-and-down')} {
  #browserToolbar {
    padding-left: calc(5px + env(safe-area-inset-left) / 4);
    padding-right: calc(5px + env(safe-area-inset-right) / 4);
  }
}
</style>
