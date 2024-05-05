<template>
  <v-combobox
    id="searchbox"
    ref="searchbox"
    v-model="query"
    v-model:menu="menu"
    :items="items"
    autofocus
    aria-label="search"
    clearable
    density="compact"
    full-width
    hide-details="auto"
    hide-selected
    :menu-props="{ maxHeight: undefined }"
    no-filter
    :prepend-inner-icon="mdiMagnify"
    variant="solo"
    @click:clear="doSearch"
    @click:prepend-inner="doSearch"
    @keydown.enter="doSearch"
    @keydown.esc="doEscape"
  />
</template>

<script>
import { mdiMagnify } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

const MAX_ITEMS = 10;

export default {
  name: "BrowserSearchCombobox",
  data() {
    return {
      mdiMagnify,
      menu: false,
      query: "",
      items: [""],
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      stateQ: (state) => state.settings.q,
    }),
  },
  watch: {
    stateQ(to) {
      this.query = to;
      this.addToMenu(to);
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings", "setIsSearchOpen"]),
    addToMenu(q) {
      if (!q || this.items.includes(q)) {
        return;
      }
      const updateditems = this.items[0] === "" ? [] : this.items;
      updateditems.unshift(q);
      this.items = updateditems.slice(0, MAX_ITEMS);
    },
    startHideTimer() {
      const q = this.query ? this.query.trim() : "";
      if (!q) {
        setTimeout(() => {
          const q = this.query ? this.query.trim() : "";
          if (!q) {
            this.setIsSearchOpen(false);
          }
        }, 5000);
      }
    },
    doSearch() {
      this.menu = false;
      const q = this.query ? this.query.trim() : "";
      this.setSettings({ q });
      this.addToMenu(q);
      this.startHideTimer();
    },
    doEscape() {
      this.menu = false;
      this.startHideTimer();
    },
  },
};
</script>

<style lang="scss" scoped>
/*
#searchbox{
  font-size: small;
}
*/
</style>
