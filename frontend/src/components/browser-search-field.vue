<template>
  <v-combobox
    ref="searchbox"
    v-model="autoquery"
    :items="queries"
    autofocus
    clearable
    dense
    aria-label="search"
    disable-lookup
    flat
    full-width
    hide-selected
    :menu-props="menuProps"
    no-filter
    solo
    :prepend-inner-icon="mdiMagnify"
    @click:prepend-inner="searchClick"
    @keydown.enter="searchClick"
    @keydown.esc="closeMenu"
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
      menuProps: {
        openOnClick: true,
        value: false,
        closeOnClick: true,
        closeOnContentClick: true,
      },
    };
  },
  computed: {
    ...mapState(useBrowserStore, {
      queries: (state) => state.page.queries,
      stateAutoquery: (state) => state.settings.autoquery,
    }),
    autoquery: {
      get() {
        return this.stateAutoquery;
      },
      set(value) {
        const autoquery = value ? value.trim() : "";
        this.setSettings({ autoquery });
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    searchClick: function () {
      const value = this.$refs["searchbox"].$refs.input.value;
      this.autoquery = value;
    },
    closeMenu: function () {
      this.$refs.searchbox.$refs.menu.isActive = false;
    },
  },
};
</script>
