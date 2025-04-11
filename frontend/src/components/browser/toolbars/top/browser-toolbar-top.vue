<template>
  <v-toolbar id="browserToolbarTop" flat density="compact" :height="48">
    <v-toolbar-items id="browserToolbarLeftItems">
      <BrowserTopGroupSelect />
      <BrowserFilterBySelect />
      <BrowserOrderBySelect />
      <BrowserOrderReverseButton />
      <BrowserSearchButton />
    </v-toolbar-items>
    <v-spacer />
    <v-toolbar-items>
      <SettingsDrawerButton />
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
