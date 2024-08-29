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
    :error-messages="searchError"
    full-width
    hide-details="auto"
    hide-selected
    :menu-props="{ maxHeight: undefined }"
    no-filter
    :prepend-inner-icon="mdiMagnify"
    variant="solo"
    @click:clear="doSearch(true)"
    @click:prepend-inner="doSearch"
    @keydown="clearSearchHideTimeout"
    @keyup.enter="doSearch"
    @keyup.esc="doBlur"
    @focus="clearSearchHideTimeout"
    @blur="doBlur"
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
      searchError: (state) => state.page.searchError,
    }),
  },
  watch: {
    stateQ(to) {
      this.query = to;
      this.addToMenu(to);
    },
  },
  beforeMount() {
    this.query = this.stateQ;
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "setSettings",
      "startSearchHideTimeout",
      "clearSearchHideTimeout",
    ]),
    addToMenu(q) {
      if (!q || this.items.includes(q)) {
        return;
      }
      const updateditems = this.items[0] === "" ? [] : this.items;
      updateditems.unshift(q);
      this.items = updateditems.slice(0, MAX_ITEMS);
    },
    doSearch(clear = false) {
      this.menu = false;
      const q = this.query ? this.query.trim() : "";
      const settings = { q };
      if (clear) {
        settings.orderBy = "sort_name";
        settings.orderReverse = false;
        this.doBlur();
      }
      this.setSettings(settings);
    },
    doBlur() {
      this.menu = false;
      const q = this.query ? this.query.trim() : "";
      if (!q) {
        this.startSearchHideTimeout();
      }
    },
  },
};
</script>
