<template>
  <v-combobox
    ref="searchbox"
    v-model="query"
    v-model:menu="menu"
    :items="queries"
    autofocus
    aria-label="search"
    clearable
    full-width
    hide-selected
    no-filter
    :prepend-inner-icon="mdiMagnify"
    @click:clear="doSearch"
    @click:prependInner="doSearch"
    @keydown.enter="doSearch"
    @keydown.esc="menu = false"
  />
</template>

<script>
import { mdiMagnify } from "@mdi/js";
import { mapActions, mapState } from "pinia";

import { useBrowserStore } from "@/stores/browser";

export default {
  name: "BrowserSearchField",
  data() {
    return {
      mdiMagnify,
      menu: false,
      query: "",
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      queries: (state) => state.page.queries,
      stateQ: (state) => state.settings.q,
    }),
  },
  watch: {
    menu(to) {
      if (!to) {
        this.doSearch(this.query);
      }
    },
    stateQ(to) {
      this.query = to;
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    doSearch() {
      this.menu = false;
      const q = this.query ? this.query.trim() : "";
      this.setSettings({ q });
    },
  },
};
</script>
