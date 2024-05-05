<template>
  <v-toolbar density="compact" :extension-height="48">
    <v-toolbar-items id="browserToolbarLeftItems">
      <BrowserTopGroupSelect />
      <BrowserOrderBySelect />
      <BrowserOrderReverseButton />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items>
      <SettingsDrawerButton />
    </v-toolbar-items>
    <template #extension>
      <v-toolbar-items id="searchToolbarItems">
        <BrowserFilterBySelect />
        <BrowserSearchCombobox />
      </v-toolbar-items>
    </template>
  </v-toolbar>
</template>

<script>
import { mdiFamilyTree, mdiMagnify } from "@mdi/js";

import BrowserFilterBySelect from "@/components/browser/toolbars/top/filter-by-select.vue";
import BrowserOrderBySelect from "@/components/browser/toolbars/top/order-by-select.vue";
import BrowserOrderReverseButton from "@/components/browser/toolbars/top/order-reverse-button.vue";
import BrowserSearchCombobox from "@/components/browser/toolbars/top/search-combobox.vue";
import BrowserTopGroupSelect from "@/components/browser/toolbars/top/top-group-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";

export default {
  name: "BrowserTopToolbar",
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
};
</script>

<style scoped lang="scss">
@use "vuetify/styles/settings/variables" as vuetify;
#browserToolbarLeftItems {
  padding-top: 4px;
}
#searchToolbarItems {
  width: 100%;
}
</style>
