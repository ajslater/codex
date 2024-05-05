<template>
  <ToolbarButton
    v-if="!isSearchOpen"
    class="searchButton"
    :icon="mdiMagnify"
    v-bind="$attrs"
    title="Search"
    @click="setIsSearchOpen(true)"
  />
</template>

<script>
import { mdiMagnify } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import ToolbarButton from "@/components/browser/toolbars/top/toolbar-button.vue";
import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowseOrderReverseButton",
  components: {
    ToolbarButton,
  },
  data() {
    return {
      mdiMagnify,
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      isSearchOpen: (state) => state.isSearchOpen,
      isQuery: (state) => Boolean(state.settings.q),
    }),
  },
  methods: {
    ...mapActions(useBrowserStore, ["setIsSearchOpen"]),
  },
};
</script>
