<template>
  <v-combobox
    ref="searchbox"
    v-model="q"
    :items="queries"
    autofocus
    clearable
    density="compact"
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
      stateQ: (state) => state.settings.q,
    }),
    q: {
      get() {
        return this.stateQ;
      },
      set(value) {
        const q = value ? value.trim() : "";
        this.setSettings({ q });
      },
    },
  },
  methods: {
    ...mapActions(useBrowserStore, ["setSettings"]),
    searchClick: function () {
      const value = this.$refs["searchbox"].$refs.input.value;
      this.q = value;
    },
    closeMenu: function () {
      this.$refs.searchbox.$refs.menu.isActive = false;
    },
  },
};
</script>
