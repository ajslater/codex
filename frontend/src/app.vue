<template>
  <v-app>
    <router-view />
  </v-app>
</template>

<script>
import { mapActions, mapState } from "pinia";

import { useAuthStore } from "@/stores/auth";
import { useSocketStore } from "@/stores/socket";

export default {
  name: "App",
  computed: {
    ...mapState(useSocketStore, {
      isConnected: (state) => state.isConnected,
    }),
    ...mapState(useAuthStore, {
      user: (state) => state.user,
    }),
  },
  watch: {
    user() {
      this.setTimezone();
    },
  },
  async created() {
    this.setTimezone();
    this.loadAdminFlags();
    this.loadProfile();
  },
  methods: {
    ...mapActions(useAuthStore, [
      "loadAdminFlags",
      "loadProfile",
      "setTimezone",
    ]),
  },
};
</script>

<!-- eslint-disable-next-line vue-scoped-css/enforce-style-type -->
<style lang="scss">
html {
  overflow-y: auto;
}

noscript {
  text-align: center;
  font-family: sans-serif;
  color: rgb(var(--v-theme-textDisabled));
}

a {
  text-decoration: none !important;
  color: rgb(var(--v-theme-primary));
}

.v-overlay__content {
  background-color: rgb(var(--v-theme-background)) !important;
  border-radius: 5px;
}

.v-tooltip > .v-overlay__content {
  color: rgb(var(--v-theme-textDisabled)) !important;
}

.highlight-table tbody > tr > td {
  border: 0;
}

.highlight-table thead > tr > th,
.highlight-table tbody > tr:nth-child(even) {
  background-color: rgb(var(--v-theme-background)) !important;
}

.codexToolbar {
  position: fixed !important;
}

.codexToolbarTitle {
  margin-inline-start: 0 !important;
}

.codexToolbarTitle > .v-toolbar-title__placeholder {
  text-align: center;
}
</style>
