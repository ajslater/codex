<template>
  <v-combobox
    id="searchbox"
    ref="searchbox"
    v-model="search"
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
      search: "",
      items: [""],
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      stateSearch: (state) => state.settings.search,
      searchError: (state) => state.page.searchError,
    }),
  },
  watch: {
    stateSearch(to) {
      this.search = to;
      this.addToMenu(to);
    },
  },
  beforeMount() {
    this.search = this.stateSearch;
  },
  methods: {
    ...mapActions(useBrowserStore, [
      "setSettings",
      "startSearchHideTimeout",
      "clearSearchHideTimeout",
    ]),
    addToMenu(search) {
      if (!search || this.items.includes(search)) {
        return;
      }
      const updateditems = this.items[0] === "" ? [] : this.items;
      updateditems.unshift(search);
      this.items = updateditems.slice(0, MAX_ITEMS);
    },
    doSearch(clear = false) {
      this.menu = false;
      const search = this?.search.trim() || "";
      const settings = { search };
      if (clear) {
        settings.orderBy = "sort_name";
        settings.orderReverse = false;
        this.doBlur();
      }
      this.setSettings(settings);
    },
    doBlur() {
      this.menu = false;
      const search = this?.search.trim() || "";
      if (!search) {
        this.startSearchHideTimeout();
      }
    },
  },
};
</script>
