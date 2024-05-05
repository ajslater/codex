<template>
  <v-toolbar density="compact" :height="52">
    <v-toolbar-items id="browserToolbarLeftItems">
      <BrowserTopGroupSelect />
      <BrowserFilterBySelect />
      <BrowserOrderBySelect />
      <BrowserOrderReverseButton />
      <BrowserSearchButton />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items>
      <SettingsDrawerButton :scale="true" />
    </v-toolbar-items>
  </v-toolbar>
</template>

<script>
import { mdiFamilyTree, mdiMagnify } from "@mdi/js";

import BrowserFilterBySelect from "@/components/browser/toolbars/top/filter-by-select.vue";
import BrowserOrderBySelect from "@/components/browser/toolbars/top/order-by-select.vue";
import BrowserOrderReverseButton from "@/components/browser/toolbars/top/order-reverse-button.vue";
import BrowserSearchButton from "@/components/browser/toolbars/top/search-button.vue";
import BrowserTopGroupSelect from "@/components/browser/toolbars/top/top-group-select.vue";
import SettingsDrawerButton from "@/components/settings/button.vue";

export default {
  name: "BrowserTopToolbar",
  components: {
    BrowserFilterBySelect,
    BrowserSearchButton,
    BrowserTopGroupSelect,
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
#browserToolbarLeftItems {
  padding-top: 4px;
}
</style>
